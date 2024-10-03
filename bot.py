import discord
from discord.ext import commands
import requests
import yt_dlp
import asyncio
import os
import random

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

#/로 명령 설정
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
        
# 재생 제어를 위한 View 정의
class PlayerControls(discord.ui.View):
    def __init__(self, voice_client):
        super().__init__()
        self.voice_client = voice_client

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
        self.voice_client.stop()
        await interaction.response.send_message("노래를 정지했습니다.", ephemeral=True)
        

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
async def 재생(ctx, url):
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 들어가 주세요!")
        return

    channel = ctx.author.voice.channel
    voice_client = await channel.connect()

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop)
        voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)

    await ctx.send(f"지금 재생 중: {player.title}", view=PlayerControls(voice_client))

# '/검색재생' 명령어에 대한 처리
@bot.command()
async def 검색재생(ctx, *, keyword):
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 들어가 주세요!")
        return

    channel = ctx.author.voice.channel
    video_url = search_youtube(keyword)

    if video_url is None:
        await ctx.send(f"'{keyword}'에 대한 검색 결과를 찾을 수 없습니다.")
        return

    voice_client = await channel.connect()

    async with ctx.typing():
        player = await YTDLSource.from_url(video_url, loop=bot.loop)
        voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)

    await ctx.send(f"'{keyword}'에 대한 검색 결과 재생 중: {player.title}")

# '/추천재생' 명령어를 추가하여 AI 기반 추천 재생 기능
@bot.command()
async def 추천재생(ctx, *, keyword):
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 들어가 주세요!")
        return

    channel = ctx.author.voice.channel
    voice_client = await channel.connect()

    # 유튜브 API를 사용하여 주어진 키워드와 관련된 비디오를 검색
    video_url = search_youtube(keyword)

    if video_url is None:
        await ctx.send(f"'{keyword}'에 대한 검색 결과를 찾을 수 없습니다.")
        return

    # 여기에 AI 추천 로직을 추가 (예: 비슷한 노래 추천)
    recommended_videos = []
    for _ in range(3):  # 3개의 추천 노래 가져오기
        similar_video_url = search_youtube(keyword + " 추천")
        if similar_video_url:
            recommended_videos.append(similar_video_url)

    if recommended_videos:
        # 추천 중 랜덤으로 하나 선택
        recommended_video = random.choice(recommended_videos)
        await ctx.send(f"추천된 노래: {recommended_video}")

        async with ctx.typing():
            player = await YTDLSource.from_url(recommended_video, loop=bot.loop)
            voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)

        await ctx.send(f"'{keyword}'와 관련된 추천 재생 중: {player.title}")
    else:
        await ctx.send("추천할 노래를 찾을 수 없습니다.")
    
# '/안녕' 명령어에 반응하는 기능
@bot.command()
async def 안녕(ctx):
    await ctx.send(f'{ctx.author.mention} 안녕?')

# 봇 실행
bot.run(TOKEN)
