import discord
from discord.ext import commands
import requests

#디스코드/api 토큰 키들
TOKEN = 'MTI4OTgwNDc0MzIwNzU1NTE2Mg.GIQ8Zs.HIyj9iBBVg60ybb0xfEBgewuM5EW04w-oM6kcE'
NEWS_API_KEY = 'fcb4a607ef834352974ce2247eb45839'

#/로 명령 설
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# 아래는 테스트로 구축함
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
        
# '/안녕' 명령어에 반응하는 기능
@bot.command()
async def 안녕(ctx):
    await ctx.send(f'{ctx.author.mention} 안녕?')

# 봇 실행
bot.run(TOKEN)
