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
        
        player = await YTDLSource.from_url(next_song, loop=bot.loop)
        guild_queues[guild_id]['voice_client'].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))

        await ctx.send(f"지금 재생 중: {player.title}")
    else:
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
        self.ctx.voice_client.stop()
        await self.ctx.voice_client.disconnect()
        await interaction.response.send_message("노래를 정지하고 음성 채널을 나갑니다.", ephemeral=True)

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
    guild_id = ctx.guild.id

    # 서버별 큐 초기화
    if guild_id not in guild_queues:
        guild_queues[guild_id] = {'queue': [], 'previous': [], 'voice_client': await channel.connect()}

    # 입력이 URL인지 여부를 체크
    if input.startswith("http://") or input.startswith("https://"):
        url = input  # 입력이 유튜브 링크일 경우
    else:
        url = search_youtube(input)  # 입력이 키워드일 경우 유튜브에서 검색

    if url is None:
        await ctx.send(f"'{input}'에 대한 검색 결과를 찾을 수 없습니다.")
        return

    # 재생 중이면 큐에 추가하고 아니면 바로 재생
    if ctx.voice_client.is_playing():
        guild_queues[guild_id]['queue'].append(url)
        await ctx.send(f"'{input}'이(가) 큐에 추가되었습니다.")
    else:
        guild_queues[guild_id]['previous'].append(url)
        await play_next(ctx)

    # 재생 제어 UI 표시
    await ctx.send("재생 제어:", view=PlayerControls(ctx))

# '/안녕' 명령어에 반응하는 기능
@bot.command()
async def 안녕(ctx):
    await ctx.send(f'{ctx.author.mention} 안녕?')

# 봇 실행
bot.run(TOKEN)

