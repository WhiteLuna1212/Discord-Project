import discord
from discord.ext import commands
import requests
import yt_dlp
import asyncio

# 디스코드/api 토큰 키들
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

# 사용자가 재생한 노래 목록과 조회한 뉴스 목록
user_song_history = {}
user_news_history = {}

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

    # 사용자 노래 이력 추가
    if ctx.author.id not in user_song_history:
        user_song_history[ctx.author.id] = []
    user_song_history[ctx.author.id].append(url)

    if not voice_client.is_playing():  # 재생 중인 노래가 없을 때만 새로운 노래 재생
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=bot.loop)
            voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)

        await ctx.send(f"지금 재생 중: {player.title}")
    else:
        await ctx.send(f"{input} 곡을 대기열에 추가했습니다.")

# '/뉴스' 명령어에 반응하여 뉴스 기사를 가져오는 기능
@bot.command()
async def 뉴스(ctx, *, query):
    url = f'https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}'
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get('articles', [])
        if articles:
            # 사용자 뉴스 이력 추가
            if ctx.author.id not in user_news_history:
                user_news_history[ctx.author.id] = []
            user_news_history[ctx.author.id].append(query)

            embed = discord.Embed(title=f"{query}에 대한 뉴스", color=0x1F8B4C)
            for article in articles[:5]:  # 최대 5개의 기사만 표시
                embed.add_field(name=article['title'], value=article['url'], inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("해당하는 기사를 찾을 수 없습니다.")
    else:
        await ctx.send("뉴스를 가져오는 중 오류가 발생했습니다.")

# '/뉴스추천' 명령어로 사용자에게 추천 뉴스 제공
@bot.command()
async def 뉴스추천(ctx):
    if ctx.author.id not in user_news_history or not user_news_history[ctx.author.id]:
        await ctx.send("추천할 뉴스가 없습니다.")
        return

    # 사용자 검색 이력 기반으로 추천 뉴스 생성 (단순히 마지막 검색어 기반으로)
    last_query = user_news_history[ctx.author.id][-1]
    await ctx.send(f"'{last_query}'에 대한 추천 뉴스 목록입니다: 이건 어떻게 되나요?")

    # 실제 추천 로직은 더 복잡할 수 있습니다.
    recommended_articles = [f"추천 기사 {i+1}: http://example.com/article{i+1}" for i in range(5)]
    await ctx.send("\n".join(recommended_articles))

# '/노래추천' 명령어로 사용자에게 추천 노래 제공
@bot.command()
async def 노래추천(ctx):
    if ctx.author.id not in user_song_history or not user_song_history[ctx.author.id]:
        await ctx.send("추천할 노래가 없습니다.")
        return

    # 사용자 재생 이력 기반으로 추천 노래 생성 (단순히 마지막 재생 노래 기반으로)
    last_song = user_song_history[ctx.author.id][-1]
    await ctx.send(f"최근에 재생한 노래 '{last_song}'를 기반으로 추천 노래 목록입니다: 이런 것은 어떠신가요?")

    # 실제 추천 로직은 더 복잡할 수 있습니다.
    recommended_songs = [f"추천 노래 {i+1}: http://example.com/song{i+1}" for i in range(5)]
    await ctx.send("\n".join(recommended_songs))

# '/안녕' 명령어에 반응하는 기능
@bot.command()
async def 안녕(ctx):
    await ctx.send(f'{ctx.author.mention} 안녕?')

# 봇 실행
bot.run(TOKEN)
