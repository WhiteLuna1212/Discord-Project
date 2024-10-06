import discord
from discord.ext import commands
import requests
import yt_dlp
import asyncio
import os

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
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

    @discord.ui.button(label="이전곡", style=discord.ButtonStyle.primary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = self.ctx.guild.id
        if guild_queues[guild_id]['previous']:
            previous_song = guild_queues[guild_id]['previous'].pop()
            guild_queues[guild_id]['queue'].insert(0, previous_song)

            self.ctx.voice_client.stop()  # 현재 곡을 멈추고 이전 곡 재생
            await play_next(self.ctx)

            await interaction.response.send_message("이전 곡을 재생합니다.", ephemeral=True)

    @discord.ui.button(label="다음곡", style=discord.ButtonStyle.success)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.ctx.voice_client.stop()  # 현재 곡을 멈추고 다음 곡 재생
        await interaction.response.send_message("다음 곡을 재생합니다.", ephemeral=True)

    @discord.ui.button(label="일시 정지", style=discord.ButtonStyle.primary

