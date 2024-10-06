import discord
from discord.ext import commands
import requests
import yt_dlp
import asyncio
import os

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
    'cookiefile': cookies_file,
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

# 음악 재생 큐 설정
guild_queues = {}

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

# 큐에 있는 다음 곡을 재생하는 함수
async def play_next(ctx):
    guild_id = ctx.guild.id
    if guild_queues[guild_id]['queue']:
        next_song = guild_queues[guild_id]['queue'].pop(0)
        guild_queues[guild_id]['previous'].append(next_song)

        print(f"다음 곡 재생 중: {next_song}")  # 로그 추가
        
        player = await YTDLSource.from_url(next_song, loop=bot.loop)
        guild_queues[guild_id]['voice_client'].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))

        await ctx.send(f"지금 재생 중: {player.title}")
    else:
        print("큐가 비어 있음. 음성 채널에서 나갑니다.")  # 로그 추가
        await guild_queues[guild_id]['voice_client'].disconnect()

# 재생 제어를 위한 View 정의
class PlayerControls(discord.ui.View):
    def __init__(self, voice_client, player_queue):
        super().__init__()
        self.voice_client = voice_client
        self.player_queue = player_queue

    @discord.ui.button(label="이전 곡", style=discord.ButtonStyle.primary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.player_queue) > 1:
            self.player_queue.pop(0)  # 현재 재생 중인 곡 제거
            next_song_url = self.player_queue[0]
            player = await YTDLSource.from_url(next_song_url, loop=bot.loop)
            self.voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)
            await interaction.response.send_message(f"이전 곡 재생 중: {player.title}", ephemeral=True)
        else:
            await interaction.response.send_message("이전 곡이 없습니다.", ephemeral=True)

    @discord.ui.button(label="일시 정지", style=discord.ButtonStyle.primary)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client.is_playing():
            self.ctx.voice_client.pause()
            await interaction.response.send_message("노래를 일시 정지했습니다.", ephemeral=True)

    @discord.ui.button(label="재개", style=discord.ButtonStyle.success)
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client.is_paused():
            self.ctx.voice_client.resume()
            await interaction.response.send_message("노래를 다시 재생합니다.", ephemeral=True)

    @discord.ui.button(label="정지", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.voice_client.stop()
        self.player_queue.clear()  # 플레이리스트 초기화
        await interaction.response.send_message("노래를 정지했습니다.", ephemeral=True)

    @discord.ui.button(label="다음 곡", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.player_queue) > 1:
            self.player_queue.pop(0)  # 현재 재생 중인 곡 제거
            next_song_url = self.player_queue[0]
            player = await YTDLSource.from_url(next_song_url, loop=bot.loop)
            self.voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)
            await interaction.response.send_message(f"다음 곡 재생 중: {player.title}", ephemeral=True)
        else:
            await interaction.response.send_message("다음 곡이 없습니다.", ephemeral=True)

# 봇이 준비되었을 때 실행되는 이벤트
@bot.event
async def on_ready():
    print(f'봇이 로그인되었습니다. {bot.user.name}')

# 뉴스 API를 이용한 기사 검색 함수
def get_news(keyword):
    url = f'https://newsapi.org/v2/everything?q={keyword}&apiKey={NEWS_API_KEY}&pageSize=5'
    response = requests.get(url)
    
    if response.status_code == 200:
        articles = response.json().get('articles')
        news_list = []
        
        for article in articles:
            title = article['title']
            url = article['url']
            news_list.append(f"{title} - {url}")
        
        return news_list
    else:
        return None

# '/뉴스' 명령어에 반응하는 기능
@bot.command()
async def 뉴스(ctx, *, keyword):
    news_list = get_news(keyword)
    
    if news_list:
        response_message = "\n".join(news_list)
        await ctx.send(f"'{keyword}'에 대한 기사 5개:\n{response_message}")
    else:
        await ctx.send("뉴스를 가져오는 데 실패했습니다.")

# '/재생' 명령어에 반응하여 유튜브 링크를 재생하는 기능
@bot.command()
async def 재생(ctx, *, input):
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 들어가 주세요!")
        return

    channel = ctx.author.voice.channel
    guild_id = ctx.guild.id

    # 서버별 큐 초기화
    if guild_id not in guild_queues:
        guild_queues[guild_id] = {'queue': [], 'previous': [], 'voice_client': None}

    # 음성 클라이언트 연결 확인 및 로그 추가
    if ctx.voice_client is None:
        print("봇이 음성 채널에 연결되지 않았습니다. 연결을 시도합니다.")  # 로그 추가
        guild_queues[guild_id]['voice_client'] = await channel.connect()

    # 플레이리스트 초기화
    if not hasattr(ctx.guild, 'player_queue'):
        ctx.guild.player_queue = []

    # URL 또는 키워드 처리
    if input.startswith("http://") or input.startswith("https://"):
        url = input
    else:
        url = search_youtube(input)

    if url is None:
        await ctx.send(f"'{input}'에 대한 검색 결과를 찾을 수 없습니다.")
        return

    # URL 추가
    ctx.guild.player_queue.append(url)

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop)
        voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)

    await ctx.send(f"지금 재생 중: {player.title}", view=PlayerControls(voice_client, ctx.guild.player_queue))

# '/안녕' 명령어에 반응하는 기능
@bot.command()
async def 안녕(ctx):
    await ctx.send(f'{ctx.author.mention} 안녕?')

# 봇 실행
bot.run(TOKEN)
