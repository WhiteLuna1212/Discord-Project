import discord
from discord.ext import commands
import requests
import yt_dlp
import asyncio

#디스코드/api 토큰 키들
TOKEN = 'MTI4OTgwNDc0MzIwNzU1NTE2Mg.GIQ8Zs.HIyj9iBBVg60ybb0xfEBgewuM5EW04w-oM6kcE'
NEWS_API_KEY = 'fcb4a607ef834352974ce2247eb45839'
YOUTUBE_API_KEY = 'AIzaSyDXTFDsD1oK0rtbfYf-F0LoRwfDJ6LZkwA'

# 쿠키 파일 경로 설정
cookies_file = 'cookies.txt'

# yt-dlp 설정
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'cookiefile': cookies_file,  # 쿠키 파일 사용
    'quiet': True,
    'no_warnings': True,
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# /로 명령 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# 유튜브에서 오디오를 추출하는 클래스
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url']
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# 유튜브 API를 이용해 키워드로 영상을 검색하는 함수
def search_youtube(query):
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&q={query}&key={YOUTUBE_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        search_results = response.json()['items']
        if len(search_results) > 0:
            video_id = search_results[0]['id']['videoId']
            return f"https://www.youtube.com/watch?v={video_id}"
        else:
            return None
    else:
        return None

# 재생 대기열을 관리하는 클래스
class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current_index = 0

    def add_song(self, song):
        self.queue.append(song)

    def next_song(self):
        if self.current_index < len(self.queue) - 1:
            self.current_index += 1
        return self.queue[self.current_index]

    def prev_song(self):
        if self.current_index > 0:
            self.current_index -= 1
        return self.queue[self.current_index]

    def current_song(self):
        return self.queue[self.current_index]

# 재생 대기열 객체 생성
music_queue = MusicQueue()

# 사용자 이력 저장을 위한 딕셔너리
user_song_history = {}
user_news_history = {}

# 유튜브 노래 추천 함수
def recommend_songs(query):
    # 'query'와 관련된 5개의 추천곡을 검색
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&q={query}&maxResults=5&key={YOUTUBE_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        search_results = response.json()['items']
        return [f"https://www.youtube.com/watch?v={item['id']['videoId']}" for item in search_results]
    else:
        return []

# 뉴스 추천 함수
def recommend_news(query):
    url = f'https://newsapi.org/v2/everything?q={query}&pageSize=5&apiKey={NEWS_API_KEY}'
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get('articles', [])
        return articles
    else:
        return []

# 재생 제어를 위한 View 정의
class PlayerControls(discord.ui.View):
    def __init__(self, voice_client):
        super().__init__()
        self.voice_client = voice_client

    @discord.ui.button(label="이전곡", style=discord.ButtonStyle.secondary)
    async def prev_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.stop()  # 현재 곡 정지
            song = music_queue.prev_song()  # 이전 곡 가져오기
            player = await YTDLSource.from_url(song, loop=bot.loop)
            self.voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)
            await interaction.response.send_message(f"이전 곡: {player.title}", ephemeral=True)

    @discord.ui.button(label="일시 정지", style=discord.ButtonStyle.primary)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            await interaction.response.send_message("노래를 일시 정지했습니다.", ephemeral=True)

    @discord.ui.button(label="재개", style=discord.ButtonStyle.success)
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            await interaction.response.send_message("노래를 다시 재생합니다.", ephemeral=True)

    @discord.ui.button(label="정지", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.voice_client.stop()  # 노래 정지
        await self.voice_client.disconnect()  # 봇이 음성 채널에서 나감
        await interaction.response.send_message("노래를 정지하고 음성 채널을 떠납니다.", ephemeral=True)

    @discord.ui.button(label="다음곡", style=discord.ButtonStyle.secondary)
    async def next_song(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.stop()  # 현재 곡 정지
            song = music_queue.next_song()  # 다음 곡 가져오기
            player = await YTDLSource.from_url(song, loop=bot.loop)
            self.voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)
            await interaction.response.send_message(f"다음 곡: {player.title}", ephemeral=True)

# 봇이 준비되었을 때 실행되는 이벤트
@bot.event
async def on_ready():
    print(f'봇이 로그인되었습니다. {bot.user.name}')

# '/재생' 명령어에 반응하여 유튜브 링크 또는 키워드로 재생하는 기능
@bot.command()
async def 재생(ctx, *, input):
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 들어가 주세요!")
        return

    channel = ctx.author.voice.channel

    # 봇이 이미 음성 채널에 연결되어 있는지 확인
    if ctx.voice_client is None:
        voice_client = await channel.connect()  # 연결되어 있지 않으면 음성 채널에 연결
    else:
        voice_client = ctx.voice_client  # 이미 연결되어 있으면 현재 연결을 사용

    # 입력이 URL인지 여부를 체크
    if input.startswith("http://") or input.startswith("https://"):
        url = input  # 입력이 유튜브 링크일 경우
    else:
        url = search_youtube(input)  # 입력이 키워드일 경우 유튜브에서 검색

    if url is None:
        await ctx.send(f"'{input}'에 대한 검색 결과를 찾을 수 없습니다.")
        return

    music_queue.add_song(url)  # 노래를 재생 대기열에 추가

    # 사용자 노래 이력 저장
    if ctx.author.id not in user_song_history:
        user_song_history[ctx.author.id] = []
    user_song_history[ctx.author.id].append(input)

    if not voice_client.is_playing():  # 재생 중인 노래가 없을 때만 새로운 노래 재생
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=bot.loop)
            voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)

        await ctx.send(f"지금 재생 중: {player.title}", view=PlayerControls(voice_client))
    else:
        await ctx.send(f"{input} 곡을 대기열에 추가했습니다.")

# '/뉴스추천' 명령어로 사용자에게 추천 뉴스 제공
@bot.command()
async def 뉴스추천(ctx):
    if ctx.author.id not in user_news_history or not user_news_history[ctx.author.id]:
        await ctx.send("추천할 뉴스가 없습니다.")
        return

    # 사용자 검색 이력 기반으로 추천 뉴스 제공
    recent_news_query = user_news_history[ctx.author.id][-1]
    recommended_articles = recommend_news(recent_news_query)
    
    if recommended_articles:
        await ctx.send(f"'{recent_news_query}'에 대한 추천 기사입니다:\n")
        for article in recommended_articles:
            await ctx.send(f"{article['title']} - {article['url']}")
    else:
        await ctx.send("추천 기사를 가져올 수 없습니다.")

# '/노래추천' 명령어로 사용자에게 추천 곡 제공
@bot.command()
async def 노래추천(ctx):
    if ctx.author.id not in user_song_history or not user_song_history[ctx.author.id]:
        await ctx.send("추천할 노래가 없습니다.")
        return

    # 최근에 들었던 노래 기반으로 추천
    recent_song_query = user_song_history[ctx.author.id][-1]
    recommended_songs = recommend_songs(recent_song_query)
    
    if recommended_songs:
        await ctx.send(f"'{recent_song_query}'에 대한 추천 곡입니다:\n")
        for song_url in recommended_songs:
            await ctx.send(song_url)
    else:
        await ctx.send("추천 곡을 가져올 수 없습니다.")

# '/안녕' 명령어에 반응하는 기능
@bot.command()
async def 안녕(ctx):
    await ctx.send(f'{ctx.author.mention} 안녕?')

# 봇 실행
bot.run(TOKEN)
