import pyupbit
import datetime
import ccxt
from binance.client import Client
import websockets
import json
import schedule
import logging
from aiogram import Bot, Dispatcher, executor, types
import math
import sqlite3
import requests
from bs4 import BeautifulSoup
import asyncio
import time
import pandas as pd
import os.path
import traceback

token='5164648575:AAG-jcEnLcUbWdZdHClAEsT9u-KPGZNHIJM'

access_upbit = "EgJ36EzOKj7q3labG8A4VemvDZwhxTbsU8ufWu73"
secret_upbit = "V8PYemvkYw5OiQwZHLC4h3f7wydLZPM7EYdRnLIH"

access_binance = "ScMaRiofWuKQ0ivkewrqJtJygKAfZPxW4D86X3hD9HVsbUO22c6wLZXOghPcGYhB"
secret_binance = "y3lE0YHIgBGJ1CLIwfVlpKD1BaMgCNLnTW4RjLy5T3HQ9Mqho2VxfmmKcTboWiyM"




# 바이낸스선물, 업비트 로그인
binance = ccxt.binance(config={
    'apiKey': "ScMaRiofWuKQ0ivkewrqJtJygKAfZPxW4D86X3hD9HVsbUO22c6wLZXOghPcGYhB", 
    'secret': "y3lE0YHIgBGJ1CLIwfVlpKD1BaMgCNLnTW4RjLy5T3HQ9Mqho2VxfmmKcTboWiyM",
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

client = Client(api_key=access_binance, api_secret=secret_binance)
#client.session.timeout=0.01


upbit = pyupbit.Upbit(access_upbit, secret_upbit)
print("autotrade start")

# 업비트 매수 사용자 정의함수
class Upbit:

    def __init__(self):
        pass
                
    def marketbuy(self, coin_ticker, amount):
       if(coin_ticker=="eth"):
        vol = upbit.buy_market_order("KRW-ETH", amount)
        uuid = vol['uuid']
        # time.sleep(0.15)
        order = upbit.get_order(uuid)
        while len(order['trades'])==0:
            order = upbit.get_order(uuid)
        
        trades = order['trades']

        volume=0 #시장가 주문시 거래가 여러번 이루어질 수 있기 때문에, 거래기록회수(trades)에 값들을 다 합해줌
        price=0
        sum_price=0
        for trade in trades:
            volume=volume + float(trade['volume'])
            sum_price=sum_price+ float(trade['volume'])*float(trade['price'])
        price = sum_price/volume
        data=[price, volume, order]
        #print("업비트 {}, 매입가격:{}, 체결수량:{}".format(coin_ticker, price, volume))
        return(data)

    def marketsell(self, coin_ticker, volume):
        # 업비트 시장가 전량매도
        if(coin_ticker=="eth"):
            sell_upbit = upbit.sell_market_order("KRW-ETH", volume)
            uuid = sell_upbit['uuid']

            order = upbit.get_order(uuid)
            while len(order['trades'])==0:
                order = upbit.get_order(uuid)
        
            trades = order['trades']
            
            volume=0 
            price=0
            sum_price=0

            #시장가 주문시 거래가 여러번 이루어질 수 있기 때문에, 거래기록회수(trades)에 값들을 다 합해줌
            for trade in trades:
                volume=volume + float(trade['volume'])
                sum_price=sum_price+ float(trade['volume'])*float(trade['price'])
            price = sum_price/volume
            data=[price, volume, order]
            #print("업비트 {}, 매도가격:{}, 체결수량:{}".format(coin_ticker, price, volume))
            return(data)
        
        
#바이낸스 주문 클래스
class Binance:
    def __init__(self):
        pass

    def marketsell(self, coin_ticker, vol, leverage):
        if(coin_ticker=="eth"):
            symbol = "ETH/USDT"
            # 바이낸스 선물 매도
            market = binance.market(symbol)
            resp = binance.fapiPrivate_post_leverage({
                'symbol': market['id'],
                'leverage': leverage
            })

            order = binance.create_market_sell_order(
                symbol=symbol,
                amount=vol,
            )
            price=order['average']
            volume=order['filled']
            data=[price, volume, order]
            #print("바이낸스선물 매도체결 {}, 가격:{}, 수량:{}".format(coin_ticker,price, volume))
            return data

    # 바이낸스 선물 매수(매도정리)
    def marketbuy(self, coin_ticker, vol):
        if(coin_ticker=="eth"):
            order = binance.create_market_buy_order(
            symbol = "ETH/USDT",
            amount=vol, 
            )
            price=order['average']
            volume=order['filled']
            data=[price, volume, order]
            #print("바이낸스선물 매수체결 {}, 가격:{}, 수량:{}".format(coin_ticker,price, volume))
            return data

class KimpT:
    def __init__(self, index, leverage):
        self.index=index
        self.leverage=leverage

    # 김프 진입 등록
    def addcoin(self, coin_ticker, amount, target):
        self.coin_ticker = coin_ticker
        self.amount = amount
        self.target = target
    
    # 김프 진입
    def BeginTrade(self, coin_ticker, amount, leverage, target):
        
        # 업비트 매수주문
        myupbit=Upbit()
        self.upbit_buy=myupbit.marketbuy(coin_ticker, amount)

        try:        
            # 바이낸스 선물거래 레버리지 설정 및 매도
            binance.load_markets()
            mybinance=Binance()
            self.binance_sell=mybinance.marketsell(coin_ticker, self.upbit_buy[1], leverage)
        except Exception as e:
            #바이낸스 거래 오류발생시 업비트 주문수량 전량 매도
            self.upbit_buy=myupbit.marketsell(coin_ticker, amount)
            self.upbit_buy[1]=0
            print(e)

        #업비트 과매수물량 cutting
        vol_diff=self.upbit_buy[1]-self.binance_sell[1]
        if vol_diff>0:
            try:
                self.upbit_sell=myupbit.marketsell(coin_ticker, vol_diff)
                self.upbit_buy[1]=self.upbit_buy[1]-self.upbit_sell[1]
            except Exception as e:
                print("과매수 cutting실패{}".format(e))
                pass

        ekp = round(( self.upbit_buy[0] / self.binance_sell[0]), 2)
        ekp2 = round(( self.upbit_buy[0] / (self.binance_sell[0]*Usdkrw) - 1 )*100, 4)
        
        

        #진입 거래 히스토리db에 등록
        now = datetime.datetime.now()
        test_tuple = (coin_ticker, self.upbit_buy[1],self.binance_sell[1],self.upbit_buy[0],self.binance_sell[0],target,ekp, ekp2)
        
        try:
            if mode==0:
                df.loc[df.Serial == self.index, ('Coin_ticker', 'Vol_buy_u', 'Vol_sell_b', 'Price_buy_u', 'Price_sell_b', 'Wish_ekp', 'Exe_ekp', 'Exe_ekp2')] = test_tuple
         
            # elif mode==1:
            #     c.executemany("INSERT OR REPLACE INTO History(Time, Serial, Coin_ticker, Vol_buy_u, Vol_sell_b, Price_buy_u, Price_sell_b, Wish_ekp2, Exe_ekp, Exe_ekp2) VALUES(?,?,?,?,?,?,?,?,?,?)",
            # test_tuple)
                

        except Exception as e:
            print("{} begin trade 히스토리db등록오류".format(e))
            fs = open("DBerror.txt","w")
            fs.writelines(e)
            fs.close()
            pass

            

        return [self.upbit_buy, self.binance_sell, ekp, ekp2]

    # 김프 탈출
    def GetoutTrade(self, coin_ticker, volU, volB, target):

        #바이낸스 매수주문
        markets = binance.load_markets()
        mybinance=Binance()
        self.binance_buy=mybinance.marketbuy(coin_ticker, volB)

        #업비트 매도주문
        myupbit=Upbit()
        self.upbit_sell=myupbit.marketsell(coin_ticker, volU)

        xkp = round(( self.upbit_sell[0] / self.binance_buy[0]),2)
        xkp2 = round(( self.upbit_sell[0] / (self.binance_buy[0]*Usdkrw) - 1)*100 ,4)

        #탈출 거래 히스토리db에 등록
        now = datetime.datetime.now()
        test_tuple = (coin_ticker, self.upbit_sell[1], self.binance_buy[1], self.upbit_sell[0], self.binance_buy[0], 
        target, xkp, xkp2)
        #try:
        if mode==0:
            df.loc[df.Serial == self.index, ('Coin_ticker', 'Vol_sell_u', 'Vol_buy_b','Price_sell_u','Price_buy_b','Wish_xkp','Exe_xkp','Exe_xkp2')] = test_tuple
            # c.close
        elif mode==1:
            pass
            # c.execute("UPDATE History SET Time=:now, Coin_ticker=:coin_ticker, Vol_sell_u=:vol_sell_u, Vol_buy_b=:vol_buy_b, Price_sell_u=:price_sell_u, Price_buy_b=:price_buy_b, Wish_xkp2=:wish_xkp2, Exe_xkp=:exe_xkp, Exe_xkp2=:exe_xkp2 WHERE Serial=:id", {"now": now, "coin_ticker": coin_ticker, "vol_sell_u":self.upbit_sell[1], "vol_buy_b":self.binance_buy[1], "price_sell_u":self.upbit_sell[0], "price_buy_b":self.binance_buy[0], "wish_xkp2":target, "exe_xkp":xkp, "exe_xkp2":xkp2, 'id': self.index})              
            
            # c.close  
        # except:
        #     pass
        

        return [self.upbit_sell, self.binance_buy, xkp, xkp2]

class Present_Kimp():
        def __init__(self):
            pass
        
        def ekp(self, coin_ticker):

            if(coin_ticker=="eth"):
                # 현재 업비트 매도호가 가져오기
                orderbook = pyupbit.get_orderbook(ticker="KRW-ETH")
                bids_asks = orderbook['orderbook_units']
                upbit_ask = float(bids_asks[0]['ask_price'])
                
                # 바이낸스 선물 매수호가 가져오기
                orderbook_b = client.futures_order_book(symbol='ETHUSDT')
                binance_bid = float(orderbook_b['bids'][0][0])
                now = datetime.datetime.now()
                
                ekp_present = round(( upbit_ask / binance_bid ),2)
                ekp_present_2 = round(( upbit_ask / (binance_bid*Usdkrw) - 1 )*100,4)

                data = [coin_ticker, ekp_present, Usdkrw, upbit_ask, binance_bid, ekp_present_2]
                return data

        def xkp(self, coin_ticker):
            if(coin_ticker=="eth"):
                # 현재 업비트 매수호가 가져오기
                orderbook = pyupbit.get_orderbook(ticker="KRW-ETH")
                bids_asks = orderbook['orderbook_units']
                upbit_bid = float(bids_asks[0]['bid_price'])

                # 바이낸스 선물 매도호가 가져오기
                orderbook_b = client.futures_order_book(symbol='ETHUSDT')
                binance_ask= float(orderbook_b['asks'][0][0])
                # now = datetime.datetime.now()             
                xkp_present = round(( upbit_bid / (binance_ask) ),2)
                xkp_present_2 = round(( upbit_bid / (binance_ask*Usdkrw) - 1 )*100,4)
                data =[coin_ticker, xkp_present, Usdkrw, upbit_bid, binance_ask, xkp_present_2]
                return data
                


async def enter(coin_ticker, amount):
    a=KimpT(index, leverage)
    enter_data=a.BeginTrade(coin_ticker, amount, leverage, 1)
    return enter_data
 

async def exit_coin(cointicker):
    if cointicker=="eth":
        # 업비트 잔량 계산후 매도주문
        remain_btc = upbit.get_balance("KRW-ETH")
        sell_upbit = upbit.sell_market_order("KRW-ETH", remain_btc)
        print(sell_upbit)
        uuid_upbit = sell_upbit['uuid']
        order = upbit.get_order(uuid_upbit)
       
        #바이낸스 잔량 조회
        balance = binance.fetch_balance()
        positions = balance['info']['positions']
        for position in positions:
            if position["symbol"] == "ETHUSDT":
                binance_volume=float(position['positionAmt'])

        #바이낸스 조회결과 매도포지션인 경우 전량 매수포지션으로 청산
        if binance_volume<0:
            vol=binance_volume*-1

            order = binance.create_market_buy_order(
            symbol = "ETH/USDT",
            amount=vol, 
            )
            price=order['average']
            volume=order['filled']
            data_b=[price, volume, order]
          
        #업비트 매도 처리기록이 잡혀지면 출력
        while len(order['trades'])==0:
            order = upbit.get_order(uuid_upbit)
        trades = order['trades']
        volume=0 
        sum_price=0

            #시장가 주문시 거래가 여러번 이루어질 수 있기 때문에, 거래기록회수(trades)에 값들을 다 합해줌
        for trade in trades:
            volume=volume + float(trade['volume'])
            sum_price=sum_price+ float(trade['volume'])*float(trade['price'])
            price = sum_price/volume
            data_u=[price, volume, order]
      

        return [data_u, data_b, 1]

# Investing.com에서 환율정보 가져오기
def get_usdkrw():
    try:
        global Usdkrw
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'text/html; charset=utf-8'
        }
        response = requests.get("https://kr.investing.com/currencies/usd-krw", headers=headers)
        content = BeautifulSoup(response.content, 'html.parser')
        containers = content.find('span', {'class': 'text-2xl'})
        currency_rate = float(containers.text.replace(',',''))
        Usdkrw = currency_rate
    except Exception as e :
        print("get_usdkrw에러 {}".format(e))
        pass


def Rualive():
    global alive
    alive=datetime.datetime.now()



index=0
try:
    find_lev=client.futures_account()
    find_lev=find_lev['positions']
    for lev in find_lev:
        if find_lev['symbol']=='ETHUSDT':
            getlev=find_lev['leverage']
            break
except:
    getlev=4
leverage = getlev

Usdkrw = 1
get_usdkrw()
Trade=[]

alive= 1
mode = 0

schedule.every(30).minutes.do(Rualive)
schedule.every(3).minutes.do(get_usdkrw)

logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=token)
dp = Dispatcher(bot)
    

# # DB 불러오기. 연결
# conn = sqlite3.connect("Addcoin_list.db", isolation_level=None)
# c = conn.cursor()


#기존에 저장한 Data가 있다면 로드 , DataFrame Serial 값이 가장 큰 값으로 i를 초기화
if os.path.isfile('Addcoin_list.csv'):
    df = pd.read_csv("Addcoin_list.csv", index_col=0)
    i=df["Serial"].max(skipna=True) + 1
else:
    # 기존에 저장한 파일이 없다면 기본 셋팅값으로 설정하고 i 값(일련번호 시작값)은 1로 초기화
    df = pd.DataFrame({'Serial': [0], 'Addcir': [0], 'Status': [0], 'Coin_ticker': ['eth'],
 'Waitamount': [0], 'Wish_ekp': [0.11], 'Wish_xkp': [0.12], 'Exe_ekp': [0.13], 'Vol_buy_u': [0.14], 
 'Vol_sell_b': [0.15], 'Wish_ekp2': [0.16], 'Wish_xkp2': [0.17], 'Exe_ekp2': [0.18], 'Exe_xkp2': [0.19],
'Price_buy_u': [0.19], 'Price_sell_b': [0.19], 'Price_sell_u': [0.19], 'Price_buy_b': [0.19], 'Vol_sell_u': [0.19], 'Vol_buy_b': [0.19],})
    i==1


# # index(거래번호) 값 초기화 : DB상 가장 아래에 있는 데이터의 시리얼넘버(인덱스)로 수정
# c.execute("Select * from Kimp_list ORDER BY ROWID DESC LIMIT 1")
# try:
#     i= int(c.fetchone()[0])+1
# except:
#     i=1
# print(i)





# 자동 진입 모듈
@dp.message_handler(commands=['0123D8CF'])
async def catcher(message: types.Message):
    client = Client(api_key=access_binance, api_secret=secret_binance)
    await message.answer("작동시작")
    global df
    #uri = "wss://api.upbit.com/websocket/v1"

    
    
    # subscribe_fmt = [{"ticket":"UNIQUE_TICKET"},{"type":"orderbook","codes":["KRW-ETH.1"]}]
    # subscribe_data = json.dumps(subscribe_fmt)
    # await websocket.send(subscribe_data)
    # conn = sqlite3.connect("Addcoin_list.db", isolation_level=None)
    # c = conn.cursor()
    #await asyncio.sleep(0.01)
    while True: 
    
        
        try:
            schedule.run_pending()
            # try:
            #     data = await websocket.recv()
            # except ConnectionError:
            #     print('Reconnecting')
            #     data = await websocket.recv()
    
            #업비트 호가 가져오기
            orderbook = pyupbit.get_orderbook("KRW-ETH")
            bids_asks = orderbook['orderbook_units']
            ask_price = bids_asks[0]['ask_price']
            bid_price = bids_asks[0]['bid_price']
            now = datetime.datetime.now()
            # 바이낸스 선물 매수호가 가져오기
            orderbook_b = client.futures_order_book(symbol='ETHUSDT')
            binance_bid = float(orderbook_b['bids'][0][0])
            binance_ask = float(orderbook_b['asks'][0][0])
            #print("현재 코인환율:{}, {}".format(data, now))
            # range = c.execute("SELECT * FROM Kimp_list")
            
            if mode==0: 
                data1 = (ask_price / binance_bid )
                data2 = (bid_price / binance_ask )

                # 데이터 추출 - 우선 2가지 조건을 만족하는 데이터 테이블을 생성
                Is_status = df['Status']==1
                Is_Wish_ekp = df['Wish_ekp'] >= data1
                Exe_data = df[Is_status & Is_Wish_ekp]
                # print(df)

                # 조건을 만족하는 테이블 각 데이터별로 김프거래 실행
                if(Exe_data.empty==False):
                    for idx, row in Exe_data.iterrows():
                        A=KimpT(row['Serial'],leverage)
                        T_data=A.BeginTrade(row['Coin_ticker'], row['Waitamount'], leverage, row['Wish_ekp'])
                        df.loc[df.Serial == row['Serial'], ('Status', 'Vol_buy_u', 'Vol_sell_b', 'Exe_ekp')] = (2, T_data[0][1], 
                        T_data[1][1], T_data[2])
                        await message.answer("거래번호:{}, {}코인 {}원 김프진입거래 실행!\n 희망진입김프:{}, 현재김프:{}\n {}\n<거래실행정보>\n업비트매수가:{}, 업비트매수수량:{}\n바이낸스매도가:{}, 바이낸스매도수량:{}\n진입김프:{}"
                        .format(row['Serial'], row['Coin_ticker'],format(row['Waitamount'],','),format(row['Wish_ekp'],','),format(round(data1,2),','),now,format(T_data[0][0],','),
                        format(T_data[0][1],','),format(T_data[1][0],','),format(T_data[1][1],','),format(T_data[2],',')))
                        #<거래실행정보>\n업비트매수가:{}, 업비트매수수량:{}\n바이낸스매도가:{}, 바이낸스매수수량:{}\n진입김프:{}"

                # 여기서부터는 탈출거래
                Is_status = df['Status']==2
                Is_Wish_xkp = df['Wish_xkp'] <= data2
                Exe_data = df[Is_status & Is_Wish_xkp]
                # print(df)

                # 조건을 만족하는 테이블 각 데이터별로 김프거래 실행
                if(Exe_data.empty==False):
                    for idx, row in Exe_data.iterrows():
                        B=KimpT(row['Serial'],leverage)
                        T_data2=B.GetoutTrade(row['Coin_ticker'], row['Vol_buy_u'], row['Vol_sell_b'], row['Wish_xkp'])
                        if row['Addcir']==1:
                            df.loc[df.Serial == row['Serial'], ('Status')] = 1
                        else:
                            df.loc[df.Serial == row['Serial'], ('Status')] = 0

                        df.loc[df.Serial == row['Serial'], ('Vol_sell_u', 'Vol_buy_b', 'Exe_xkp')] = (T_data2[0][1], 
                        T_data2[1][1], T_data2[2])
                        
                        upbit_profit=(df.at[idx,'Price_sell_u']-df.at[idx,'Price_buy_u'])*df.at[idx,'Vol_sell_u'] #업비트 거래손익
                        upbit_fee=(df.at[idx,'Price_sell_u']*df.at[idx,'Vol_sell_u']+df.at[idx,'Price_buy_u']*df.at[idx,'Vol_buy_u'])*0.0005
                        upbit_net_profit=upbit_profit-upbit_fee
                        binance_profit=(df.at[idx,'Price_sell_b']-df.at[idx,'Price_buy_b'])*df.at[idx,'Vol_sell_b']
                        binance_fee=(df.at[idx,'Price_sell_b']*df.at[idx,'Vol_sell_b']+df.at[idx,'Price_buy_b']*df.at[idx,'Vol_buy_b'])*0.0004
                        binance_net_profit=binance_profit-binance_fee
                        binance_net_profit_coinfx=round(binance_net_profit*df.at[idx,'Exe_xkp'],)
                        final_profit=round(upbit_net_profit+binance_net_profit_coinfx,)


                        await message.answer("거래번호:{}, {}코인 김프탈출거래 실행!\n 희망탈출김프:{}, 현재김프:{}\n{}\n<거래실행정보>\n업비트매도가:{}, 업비트매도수량:{}\n바이낸스매수가:{}, 바이낸스매수수량:{}\n탈출김프:{}"
                        .format(row['Serial'],row['Coin_ticker'],format(row['Wish_xkp'],','),format(round(data2,2),','), now,format(T_data2[0][0],','),format(T_data2[0][1],','),
                        format(T_data2[1][0],','),format(T_data2[1][1],','),format(T_data2[2],',')))
                        await message.answer("업비트 거래총손익:KRW {}\n바이낸스 거래총손익:USD {}\n바이낸스탈출김프기준 거래원화손익:KRW {}\n탈출김프기준 최종손익:KRW {}"
                        .format(upbit_net_profit,binance_net_profit,format(binance_net_profit_coinfx,','),format(final_profit,',')))
                        
            
                
            # elif mode==1:
            #     data1 = ( ask_price / (binance_bid*Usdkrw) - 1 )*100
            #     data2 = ( bid_price / (binance_ask*Usdkrw) - 1 )*100
            #     for data in range:
            #         # await message.answer("data:{}".format(data))
            #         # await message.answer("data[5]:{}".format(data[5]))
        
            #         if data[2]==1 and data1<=data[13]:
            #             A=KimpT(data[0],leverage)
            #             T_data=A.BeginTrade(data[3], data[4], leverage,data[13])
            #             # print("거래번호:{}, {}코인 {}원 김프진입거래 실행!, 희망진입김프:{}, 현재김프:{} {}"
            #             # .format(data[0],data[3],data[4],data[5],data,now))
            #             # c.execute("UPDATE Kimp_list SET Status=:status WHERE Serial=:id", {"status": 2, 'id': data[0]})
            #             # c.execute("UPDATE Kimp_list SET Vol_buy_u=:vol_u, Vol_sell_b=:vol_b, Exe_ekp=:exe_ekp, Exe_ekp2=:exe_ekp2 WHERE Serial=:id", {"vol_u": T_data[0][1], "vol_b":T_data[1][1], "exe_ekp":T_data[2], "exe_ekp2":T_data[3], 'id': data[0]})
                        
                        
            #             await message.answer("거래번호:{}, {}코인 {}원 김프진입거래 실행!\n 희망진입김프:{}, 현재김프:{}\n {}\n<거래실행정보>\n업비트매수가:{}, 업비트매수수량:{}\n바이낸스매도가:{}, 바이낸스매도수량:{}\n진입김프:{}, {}"
            #             .format(data[0],data[3],format(data[4],','),format(data[13],','),format(round(data1,2),','),now,format(T_data[0][0],','),format(T_data[0][1],','),format(T_data[1][0],','),format(T_data[1][1],','),format(T_data[2],','),round(T_data[3],4)))
            #             #<거래실행정보>\n업비트매수가:{}, 업비트매수수량:{}\n바이낸스매도가:{}, 바이낸스매수수량:{}\n진입김프:{}"
            #         if data[2]==2 and data2>=data[14]:
            #             # print("거래번호:{}, {}코인 김프탈출거래 실행!, 희망탈출김프:{}, 현재김프:{} {}"
            #             # .format(data[0],data[3],data[6],data, now))
            #             B=KimpT(data[0],leverage)
            #             T_data2=B.GetoutTrade(data[3], data[8], data[9],data[14])

            #             if data[1]==True:
            #                 c.execute("UPDATE Kimp_list SET Status=:status WHERE Serial=:id", {"status": 1, 'id': data[0]})
                            
            #                 # c.close
            #                 #c.execute("UPDATE Kimp_list SET Status=:status WHERE Serial=:id", {"status": 1, 'id': data[0]})
            #             else:
            #                 c.execute("UPDATE Kimp_list SET Status=:status WHERE Serial=:id", {"status": 0, 'id': data[0]})
                            
            #                 # c.close
                        
                        
            #             c.execute("SELECT * FROM History WHERE Serial=:Id", {"Id": data[0]})
                        
            #             # c.close

            #             data3=c.fetchone()
                        
            #             upbit_profit=(data3[9]-data3[7])*data3[5] #업비트 거래손익
            #             upbit_fee=(data3[7]*data3[3]+data3[9]*data3[5])*0.0005
            #             upbit_net_profit=upbit_profit-upbit_fee
            #             binance_profit=(data3[8]-data3[10])*data3[6]
            #             binance_fee=(data3[10]*data3[6]+data3[8]*data3[4])*0.00036
            #             binance_net_profit=binance_profit-binance_fee
            #             binance_net_profit_coinfx=round(binance_net_profit*data3[14],)
            #             final_profit=round(upbit_net_profit+binance_net_profit_coinfx,)
            #             exe_xkp=round(T_data2[3],4)
            #             present_xkp=round(data2,2)
            #             await message.answer("거래번호:{}, {}코인 김프탈출거래 실행!\n 희망탈출김프:{}, 현재김프:{}\n{}\n<거래실행정보>\n업비트매도가:{}, 업비트매도수량:{}\n바이낸스매수가:{}, 바이낸스매수수량:{}\n탈출김프:{}, {}"
            #             .format(data[0],data[3],format(data[13],','),format(present_xkp,','), now,format(T_data2[0][0],','),format(T_data2[0][1],','),format(T_data2[1][0],','),format(T_data2[1][1],','),format(T_data2[2],','),exe_xkp))
            #             await message.answer("업비트 거래총손익:KRW {}\n바이낸스 거래총손익:USD {}\n바이낸스탈출김프기준 거래원화손익:KRW {}\n탈출김프기준 최종손익:KRW {}"
            #             .format(upbit_net_profit,binance_net_profit,format(binance_net_profit_coinfx,','),format(final_profit,',')))
                        
            #             #<거래실행정보>\n업비트매도가:{}, 업비트매도수량:{}\n바이낸스매수가:{}, 바이낸스매수수량:{}\n진입김프:{}
                        
            #             c.execute("UPDATE Kimp_list SET Vol_sell_u=:vol_u, Vol_buy_b=:vol_b, Exe_xkp=:exe_xkp, Exe_xkp2=:exe_xkp2 WHERE Serial=:id", {"vol_u": T_data2[0][1], "vol_b":T_data2[1][1], "exe_xkp":T_data2[2], 'id': data[0], 'exe_xkp2': T_data2[3]})
            
            #업비트 api rest 제한 방지용 최소 타임 슬립            
            await asyncio.sleep(0.05)
                        # c.close
                        #c.execute("UPDATE Kimp_l
            # c.close  

        #TRY문 삭제부분    
        except requests.exceptions.ConnectTimeout:
            df.to_csv("Addcoin_list.csv", mode='w')
            await asyncio.sleep(4)
            await message.answer("catcher예외실행. ConnectionTimeout")
            await catcher(message)

        except requests.exceptions.ReadTimeout:
            df.to_csv("Addcoin_list.csv", mode='w')
            await asyncio.sleep(4)
            await message.answer("catcher예외실행. ReadTimeout")
            
            await catcher(message)
        except ConnectionError:
            df.to_csv("Addcoin_list.csv", mode='w')
            await asyncio.sleep(4)
            await message.answer("catcher ConnectionError")
            
            await catcher(message)
        except Exception as e:
            if str(e) == "('Connection aborted.', OSError(\"(104, 'ECONNRESET')\"))":
                df.to_csv("Addcoin_list.csv", mode='w')
                await message.answer("OSError 104 재시작 {}".format(e))
                await catcher(message)
            else:
                df.to_csv("Addcoin_list.csv", mode='w')
                traceback_str = ''.join(traceback.format_tb(e.__traceback__))
                await message.answer("catcher 오류발생 반복문 탈출{}\n{}".format(e, traceback_str))
                break
        
            
                
binance.load_leverage_brackets

                        
@dp.message_handler(commands=['mar'])
async def mar(message: types.Message):
    
    symbol = ['ETH/USDT']
    data= binance.fetch_account_positions(symbol)
    try:
        liquidation=float(data[0]['liquidationPrice'])
        # liquidation=format(round(liquidation,),',')
        btc_p = binance.fetch_ticker("ETH/USDT")
        liq_rate = round((liquidation/btc_p-1)*100,2)
    except:
        liquidation=0
        btc_p =0
        liq_rate=0
        
        
    await message.answer("청산가 :{}\n현재가 :{}\n청산가격괴리율:{}".format(liquidation,btc_p, liq_rate))                        


    # except:
    #     try:
    #         uri = "wss://api.upbit.com/websocket/v1"

    #         async with websockets.connect(uri,  ping_interval=None) as websocket:
            
    #             subscribe_fmt = [{"ticket":"UNIQUE_TICKET"},{"type":"orderbook","codes":["KRW-ETH.1"]}]
    #             subscribe_data = json.dumps(subscribe_fmt)
    #             await websocket.send(subscribe_data)
    #             conn = sqlite3.connect("Addcoin_list.db", isolation_level=None)
    #             c = conn.cursor()
    #             #await asyncio.sleep(0.01)
    #             while True:
    #                 schedule.run_pending()
    #                 try:
    #                     data = await websocket.recv()
    #                 except ConnectionError:
    #                     print('Reconnecting')
    #                     data = await websocket.recv()
            
                    
                    
    #                 data = json.loads(data)
    #                 data = data['orderbook_units']
    #                 ask_price = data[0]['ask_price']
    #                 bid_price = data[0]['bid_price']
    #                 now = datetime.datetime.now()
    #                 # 바이낸스 선물 매수호가 가져오기
    #                 orderbook_b = client.futures_order_book(symbol='ETHUSDT')
    #                 binance_bid = float(orderbook_b['bids'][0][0])
    #                 binance_ask = float(orderbook_b['asks'][0][0])
    #                 data = ( ask_price / binance_bid )
    #                 data2 = (bid_price / binance_ask )
    #                 #print("현재 코인환율:{}, {}".format(data, now))
    #                 range = c.execute("SELECT * FROM Kimp_list")
    #                 for data in range:
    #                     if data[2]==1 and data<=data[5]:
    #                         A=KimpT(data[0],leverage)
    #                         T_data=A.BeginTrade(data[3], data[4], leverage,data[5])
    #                         # print("거래번호:{}, {}코인 {}원 김프진입거래 실행!, 희망진입김프:{}, 현재김프:{} {}"
    #                         # .format(data[0],data[3],data[4],data[5],data,now))
    #                         c.execute("UPDATE Kimp_list SET Status=:status, Vol_buy_u=:vol_u, Vol_sell_b=:vol_b, Exe_ekp=:exe_ekp WHERE Serial=:id", {"status": 2, "vol_u": T_data[0][1], "vol_b":T_data[1][1], "exe_ekp":T_data[2], 'id': data[0]})
    #                         await message.answer("거래번호:{}, {}코인 {}원 김프진입거래 실행!\n 희망진입김프:{}, 현재김프:{}\n {}\n<거래실행정보>\n업비트매수가:{}, 업비트매수수량:{}\n바이낸스매도가:{}, 바이낸스매도수량:{}\n진입김프:{}"
    #                         .format(data[0],data[3],format(data[4],','),format(data[5],','),format(round(data,2),','),now,format(T_data[0][0],','),format(T_data[0][1],','),format(T_data[1][0],','),format(T_data[1][1],','),format(T_data[2],',')))
    #                         #<거래실행정보>\n업비트매수가:{}, 업비트매수수량:{}\n바이낸스매도가:{}, 바이낸스매수수량:{}\n진입김프:{}"
    #                     if data[2]==2 and data2>=data[6]:
    #                         # print("거래번호:{}, {}코인 김프탈출거래 실행!, 희망탈출김프:{}, 현재김프:{} {}"
    #                         # .format(data[0],data[3],data[6],data, now))
    #                         B=KimpT(data[0],leverage)
    #                         T_data2=B.GetoutTrade(data[3], data[8], data[9],data[6])
                            
    #                         await message.answer("거래번호:{}, {}코인 김프탈출거래 실행!\n 희망탈출김프:{}, 현재김프:{}\n{}\n<거래실행정보>\n업비트매도가:{}, 업비트매도수량:{}\n바이낸스매수가:{}, 바이낸스매수수량:{}\n탈출김프:{}"
    #                         .format(data[0],data[3],format(data[6],','),format(round(data,2),','), now,format(T_data2[0][0],','),format(T_data2[0][1],','),format(T_data2[1][0],','),format(T_data2[1][1],','),format(T_data2[2],',')))
    #                         #<거래실행정보>\n업비트매도가:{}, 업비트매도수량:{}\n바이낸스매수가:{}, 바이낸스매수수량:{}\n진입김프:{}
    #                         if data[1]==True:
    #                             c.execute("UPDATE Kimp_list SET Status=:status, Vol_sell_u=:vol_u, Vol_buy_b=:vol_b, Exe_xkp=:exe_xkp WHERE Serial=:id", {"status": 1, "vol_u": T_data2[0][1], "vol_b":T_data2[1][1], "exe_xkp":T_data2[2], 'id': data[0]})
    #                             #c.execute("UPDATE Kimp_list SET Status=:status WHERE Serial=:id", {"status": 1, 'id': data[0]})
    #                         else:
    #                             c.execute("UPDATE Kimp_list SET Status=:status, Vol_sell_u=:vol_u, Vol_buy_b=:vol_b, Exe_xkp=:exe_xkp WHERE Serial=:id", {"status": 0, "vol_u": T_data2[0][1], "vol_b":T_data2[1][1], "exe_xkp":T_data2[2], 'id': data[0]})
    #                             #c.execute("UPDATE Kimp_list SET Status=:status WHERE Serial=:id", {"status": 0, 'id': data[0]})
                            
    #                         c.execute("SELECT * FROM History WHERE Serial=:Id", {"Id": data[0]})
    #                         data=c.fetchone()
    #                         upbit_profit=(data[9]-data[7])*data[5] #업비트 거래손익
    #                         upbit_fee=(data[7]*data[3]+data[9]*data[5])*0.0005
    #                         upbit_net_profit=upbit_profit-upbit_fee
    #                         binance_profit=(data[8]-data[10])*data[6]
    #                         binance_fee=(data[10]*data[6]+data[8]*data[4])*0.00036
    #                         binance_net_profit=binance_profit-binance_fee
    #                         binance_net_profit_coinfx=binance_net_profit*data[14]
    #                         final_profit=upbit_net_profit+binance_net_profit_coinfx
    #                         await message.answer("업비트 거래총손익:{}\n바이낸스 거래총손익:{}\n바이낸스탈출김프기준 거래원화손익:{}\n탈출김프기준 최종손익:{}"
    #                         .format(upbit_net_profit,binance_net_profit,binance_net_profit_coinfx,final_profit))
    #     except:
    #         await message.answer("catcher 오류발생. 0123D8CF")
                        

#김프타겟에 자동거래할 것 등록하기, 등록된 목록 조회하기
@dp.message_handler(commands=['addcoin'])
async def addcoin(message: types.Message):
    global i
    global df
    if mode==0:
        #/addcoin eth,1235,0.7,100000,반복
        # 데이터 집어넣기
        split1=message.text.split("/addcoin")
        split2= split1[1].split(',',5)
        coin_ticker=split2[0].strip()
        Addcir=False

        if coin_ticker:
            try:
                if(split2[4].strip()=="반복"):
                    Addcir=True
                    ekp=round(float(split2[1].strip()),2)
                    xkp=round(float(ekp)*(1+(float(split2[2].strip())/100)),2)
                    amount=int(split2[3].strip())
                 
            except:
                try:
                    ekp=round(float(split2[1].strip()),2)
                    xkp=round(float(ekp)*(1+(float(split2[2].strip())/100)),2)
                    amount=int(split2[3].strip())
                 
                except:
                    await message.answer('입력값이 잘못되었습니다.')

            try:
                
                df2 = pd.DataFrame({'Serial': [i], 'Addcir': [Addcir], 'Status': [1], 'Coin_ticker': [coin_ticker],
                'Waitamount': [amount], 'Wish_ekp': [ekp], 'Wish_xkp': [xkp]})
                df=pd.concat([df, df2], ignore_index=True)
                # c.close
                i=i+1
                await message.answer("거래가 등록되었습니다. 코인종류:{} , 희망진입코인환율:{}, 희망탈출코인환율:{}, 금액:{}".format(coin_ticker, ekp, xkp, format(amount,",")))           
            except Exception as e:
                await message.answer('입력값이 잘못되었습니다.{}'.format(e))
        try:
            lines = "사용방법 ex) /addcoin eth, 1235, 0.7, 1000000, 반복\n/addcoin 코인종류, 희망진입코인환율, 희망수익률퍼센트, 진입할금액,반복여부(생략가능)\n"
            lines2 = "<현재 등록된 거래목록>"
            data=[]
            data=lines+lines2

            for idx, row in df.iterrows():
                if row['Status']==0:
                    stat="거래종료됨"
                elif row['Status']==1:
                    stat="진입대기"
                elif row['Status']==2:
                    stat="탈출대기"
                if row['Addcir']==True:
                    cir="반복"
                else :
                    cir="없음"

                line="\n거래번호 :{}, 코인: {}, 반복여부:{}\n Low(wish):{}, High(wish):{}\n Low(real):{}, High(real):{}\n진입여부:{}, 금액:{}\n".format(row['Serial'],
                row['Coin_ticker'],cir,row['Wish_ekp'],row['Wish_xkp'],row['Exe_ekp'],row['Exe_xkp'],stat,format(round(row['Waitamount']),","))
                data=data+line
            await message.answer(data)
        except Exception as e:
            await message.answer("addcoin함수에러 {}".format(e))
    elif mode==1:
        pass
        # # 데이터 집어넣기 /addcoin eth, 1.5, 2.5, 30000, 반복
        # split1=message.text.split("/addcoin")
        # split2= split1[1].split(',',5)
        # coin_ticker=split2[0].strip()
        # Addcir=False

        # if coin_ticker:
        #     try:
        #         if(split2[4].strip()=="반복"):
        #             Addcir=True
        #             ekp=float(split2[1].strip())
        #             xkp=float(split2[2].strip())
        #             amount=int(split2[3].strip())
        #             test_tuple = (
        #             (i, Addcir, 1, coin_ticker, amount, ekp, xkp),
        #         )
        #     except:
        #         try:
        #             ekp=float(split2[1].strip())
        #             xkp=float(split2[2].strip())
        #             amount=int(split2[3].strip())
        #             test_tuple = (
        #             (i, Addcir, 1, coin_ticker, amount, ekp, xkp),
        #         )
        #         except:
        #             await message.answer('입력값이 잘못되었습니다.')

        # try:
        #     c.executemany("INSERT INTO Kimp_list(Serial, Addcir, Status, Coin_ticker, Waitamount, Wish_ekp2, Wish_xkp2) VALUES(?,?,?,?,?,?,?)",
        #     test_tuple)
        #     # c.close
        #     i=i+1
        #     await message.answer("거래가 등록되었습니다. 코인종류:{} , 희망진입김프:{}, 희망탈출김프:{}, 금액:{}".format(coin_ticker, ekp, xkp, format(amount,",")))           
        # except :
        #     await message.answer('입력값이 잘못되었습니다.')
        # try:
        #     result = []
        #     for row in c.execute('SELECT * FROM Kimp_list'):
        #         line=[]
        #         for subrow in row:
        #             line.append(subrow)
        #         # result.append(subrow[0])
        #         # result.append(subrow[1])
        #         result.append(line)
            
        #     lines = "사용방법 ex) /addcoin eth, 1.2, 2.5, 1000000, 반복\n/addcoin 코인종류, 희망진입김프, 희망탈출김프, 진입할금액,반복여부(생략가능)\n"
        #     lines2 = "<현재 등록된 거래목록>"
        #     data=[]
        #     data=lines+lines2
        #     for row in result:
        #         if row[2]==0:
        #             stat="거래종료됨"
        #         elif row[2]==1:
        #             stat="진입대기"
        #         elif row[2]==2:
        #             stat="탈출대기"
        #         if row[1]==True:
        #             cir="반복"
        #         else :
        #             cir="없음"

        #         line="\n거래번호 :{}, 코인: {}, 반복여부:{}\n Low(wish):{}, High(wish):{}\n Low(real):{}, High(real):{}\n진입여부:{}, 금액:{}\n".format(row[0],row[3],cir,row[13],row[14],row[15],row[16],stat,format(round(row[4]),","))
        #         data=data+line
        #     await message.answer(data)
        # except Exception as e:
        #     await message.answer("addcoin함수에러".format(e))
#addcoin 리스트 중 제거
@dp.message_handler(commands=['rmcoin'])
async def rmcoin(message: types.Message):
    global df
    split1=message.text.split("/rmcoin")
    split2= split1[1].split(',',10)
    #index= int(split1[1].strip())  #거래번호만 추출
    lines = ""
    lines2 = ""
    data=[]
    data=lines+lines2
    try:
        # # 데이터 삭제
        for index in split2:
            idx = df.index[df['Serial'] == int(index.strip())].tolist()
            df= df.drop(idx, axis=0)
            data=data+", "+str(index.strip())
        await message.answer("거래번호 {}가 삭제되었습니다.".format(data))

    except Exception as e:
        await message.answer("입력 값이 잘못되었습니다.{}".format(e))
        
#반복거래 여부변경
@dp.message_handler(commands=['cghcir'])
async def cghcir(message: types.Message):
    # 데이터 집어넣기
    split1=message.text.split("/cghcir")
    if split1[1]=="":
        await message.answer("예) /cghcirf 5, 반복 or /cghcir 5, 반복해제")
        cir=""
    else:
        split2= split1[1].split(',',5)
        index= int(split2[0].strip())
        cir= split2[1].strip()

    if cir=="반복":
        df.loc[df.Serial == index, ('Addcir')] = True
        await message.answer("거래번호{}가 반복거래로 변경되었습니다.".format(index))
    elif cir=="반복해제":
        df.loc[df.Serial == index, ('Addcir')] = False
        await message.answer("거래번호{}가 반복해제로 변경되었습니다.".format(index))
    else:
        await message.answer("예) /cghcir 5, 반복 or /cghcir 5, 반복해제")

#addcoin 등록된 건의 탈출 김프 변경 
@dp.message_handler(commands=['cgh'])
async def cgh(message: types.Message):
    try:
        # # 데이터 수정
        split1=message.text.split("/cgh")
        split2= split1[1].split(',',2)
        index=int(split2[0].strip())
        cgh=float(split2[1].strip())
        df.loc[df.Serial == index, ('Wish_xkp')] = cgh
        await message.answer("거래번호{}의 탈출김프가 {}로 성공적으로 변경되었습니다.".format(index,cgh))
        
    except Exception as e:
        await message.answer("입력 값이 잘못되었습니다.{}".format(e))
        
@dp.message_handler(commands=['cgh2'])
async def cgh2(message: types.Message):
    try:
        # # 데이터 수정
        split1=message.text.split("/cgh2")
        split2= split1[1].split(',',2)
        index=int(split2[0].strip())
        cgh=float(split2[1].strip())
        print(index)
        print(cgh)
        df.loc[df.Serial == index, ('Wish_xkp2')] = cgh
        await message.answer("거래번호{}의 탈출김프가 {}로 성공적으로 변경되었습니다.".format(index,cgh))
        
    except Exception as e:
        await message.answer("입력 값이 잘못되었습니다.{}".format(e))

@dp.message_handler(commands=['ekp'])
async def send_ekp(message: types.Message):
    ekp = Present_Kimp().ekp("eth")
    await message.answer("코인 종류 : {}, 현재 진입가능코인환율 : {}, 환율 : {} \n업비트 매도호가 : {} , 바이낸스선물 매수호가 : {}\n현재 김프률 : {}"
    .format(ekp[0],format(ekp[1],','), format(ekp[2],','),format(math.trunc(ekp[3]),','),format(ekp[4],','),ekp[5]) )


@dp.message_handler(commands=['xkp'])
async def send_xkp(message: types.Message):
    xkp = Present_Kimp().xkp("eth")
    await message.answer("코인 종류 : {}, 현재 탈출가능코인환율 : {}, 환율 : {} \n업비트 매수호가 : {} , 바이낸스선물 매도호가 : {}\n현재 김프률 : {}"
    .format(xkp[0],format(xkp[1],','), format(xkp[2],','),format(math.trunc(xkp[3]),','),format(xkp[4],','),xkp[5]) )

@dp.message_handler(commands=['enter'])
async def enter_btc(message: types.Message):
    
    split1=message.text.split("/enter")
    split2= split1[1].split(',',1)
    coin_ticker=split2[0].strip()
    amount=int(split2[1].strip())

    #거래실행
    result = await enter(coin_ticker, amount)
    print(result)
    #데이터 수집
    upbit_buy=result[0]
    binance_sell=result[1]
    exchange = result[2]
    kimp = ((upbit_buy[0]/(binance_sell[0]*exchange))-1)*100
    print(upbit_buy)
    print(binance_sell)
    print(exchange)
    print(upbit_buy[0])
    print(upbit_buy[1])
    print(binance_sell[0])
    print(binance_sell[1])

    #결과 출력
    await message.answer("거래번호 : \n 업비트 매수가격 :{}, 업비트 매수수량 :{} \n 바이낸스 매도가격:{}, 바이낸스 매도수량:{} \n 진입코인환율 : {:.4f}% 환율 : {}"
    .format(format(math.trunc(round(upbit_buy[0])),','), upbit_buy[1], format(binance_sell[0],','), binance_sell[1], kimp, exchange))

@dp.message_handler(commands=['exit'])
async def exit_btc(message: types.Message):
    try:
        split1=message.text.split("/exit")
        split2= split1[1].split(',',1)
        coin_ticker=split2[0].strip()
        
        #거래실행
        result = await exit_coin(coin_ticker)
        
        #데이터 수집
        upbit_sell=result[0]
        binance_buy=result[1]
        exchange = result[2]
        kimp = (upbit_sell[0]/(binance_buy[0]))


        #결과 출력
        await message.answer("거래번호 : \n 업비트 매도가격 :{}, 업비트 매도수량 :{} \n 바이낸스 매수가격:{}, 바이낸스 매수수량:{} \n 탈출코인환율 : {}% 환율 : {}"
        .format(format(math.trunc(round(upbit_sell[0])),','), upbit_sell[1], format(binance_buy[0],','), binance_buy[1], format(kimp,','), exchange))
    except Exception as e :
        await message.answer("에러발생 {}".format(e))



@dp.message_handler(commands=['lev'])
async def lev(message: types.Message):
    try:
        split1=message.text.split("/lev")
        split2= int(split1[1].strip())

        binance.load_markets()
        global leverage
        leverage=split2

        symbol = "ETH/USDT"
        market = binance.market(symbol)
        binance.fapiPrivate_post_leverage({
            'symbol': market['id'],
            'leverage': leverage
        })

        await message.answer("ex) /lev 3\n 현재 설정된 레버리지: {}배\n마진모드 : Cross모드".format(leverage))
      
    except Exception as e:
        await message.answer("입력값이 잘못되었습니다. ex) /lev 3 정수만 입력 {}".format(e))
      
@dp.message_handler(commands=['bal'])
async def bal(message: types.Message):
    try:
        p_kimp_btc=1
        get_usdkrw()
        balance = binance.fetch_balance()
        b_free=round(balance['USDT']['free'],2) #바이낸스 사용가능 usdt
        b_used=round(balance['USDT']['used'],2) #바이낸스 진입된 usdt
        b_total=round(balance['USDT']['total'],2) #바이낸스 총 usdt
        b_total_krw=round(b_total*Usdkrw*p_kimp_btc,) #현재 비트코인김프로 계산한 바이낸스 총 krw(김프적용)

        #업비트 잔고 조회
        upbit_balance=upbit.get_balances()
        sum=0
        for data in upbit_balance:
            try:
                if data['currency']=='KRW':
                    sum+=float(data['balance'])
                else:
                    try:
                        z="KRW-"+data['currency']
                        price = pyupbit.get_current_price(z)
                    except:
                        price=0
                    sum+=float(data['balance'])*price
            except:
                pass
        sum=round(sum,)
        upbit_free=round(float(upbit_balance[0]['balance']),) #업비트 사용가능 원화
        upbit_used=sum-upbit_free #업비트 진입된 원화
        p_kimp_btc=round((p_kimp_btc-1)*100,2)
        all_krw=sum+b_total_krw
        await message.answer("적용 김프:{}\n바이낸스 사용가능 USDT:{}\n 바이낸스 진입된 USDT:{}\n 바이낸스 총 USDT:{}\n 바이낸스 현재평균김프계산 총KRW:{}\n\n업비트 사용가능 KRW:{}\n업비트 진입된 KRW:{}\n 업비트 총 KRW:{}\n\n 업비트,바이낸스(김프계산) 총 KRW:{}"
        .format(p_kimp_btc,format(b_free,','), format(b_used,','), format(b_total,','), format(b_total_krw,','),format(upbit_free,','),format(upbit_used,','),format(sum,','),format(all_krw,',')))
    except Exception as e:
        await message.answer("오류발생 {}".format(e))

# 루프문 살아있는지 확인
@dp.message_handler(commands=['alive'])
async def Isalive(message: types.Message):
    await message.answer(alive)

@dp.message_handler(commands=['mode'])
async def modee(message: types.Message):
    global mode
    
    try:
        # print(mode)
        # c.execute('SELECT * FROM Kimp_list')
        # data=c.fetchone()
        # if data:
        #     await message.answer("addcoin에 등록된 목록이 있으면 모드를 변경하실 수 없습니다.")
        # else:
            split1=message.text.split("/mode")
            split2= int(split1[1].strip())
            if split2==1 or split2==0:
                
                mode=split2
                data=""
                if mode==0:
                    data="코인환율접근(기본)"
                else:
                    data="김프률 접근"

                await message.answer("ex) /mode 1(김프률접근), /mode 0(코인환율접근\n 현재 설정된 모드: {}".format(data))
            else:
                await message.answer("ex) /mode 1(김프률접근), /mode 0(코인환율접근\n 현재 설정된 모드: {}\n 1또는 0을 입력하셔야 합니다.".format(data))
    
    except :
        await message.answer("/mode 1 김프률 접근방식\n/mode 0 코인환율 접근방식 \n현재설정된접근방식:{} ".format(mode))

@dp.message_handler(commands=['history'])
async def History(message: types.Message):
    
    df.to_csv("Addcoin_list.csv", mode='w')
    await message.answer("저장완료 {}")

# 해당거래 강제 종료 
@dp.message_handler(commands=['execoin'])
async def execoin(message: types.Message):
    try:
        split1=message.text.split("/execoin")
        split2= split1[1].split(',',10)
        if split2:
            index= int(split2[0].strip())
            Idx=df.index[df['Serial']==index].tolist()[0]
   
            # c.close
            if df.iloc[Idx]['Status']==2:
                B=KimpT(df.iloc[Idx]['Serial'],leverage)
                T_data2=B.GetoutTrade(df.iloc[Idx]['Coin_ticker'], df.iloc[Idx]['Vol_buy_u'], df.iloc[Idx]['Vol_sell_b'],df.iloc[Idx]['Wish_xkp'])

                df.loc[Idx, ('Status', 'Addcir')] = (1, 0)

                now = datetime.datetime.now()
      
                # c.close
                upbit_profit=(df.at[Idx,'Price_sell_u']-df.at[Idx,'Price_buy_u'])*df.at[Idx,'Vol_sell_u'] #업비트 거래손익
                upbit_fee=(df.at[Idx,'Price_sell_u']*df.at[Idx,'Vol_sell_u']+df.at[Idx,'Price_buy_u']*df.at[Idx,'Vol_buy_u'])*0.0005
                upbit_net_profit=upbit_profit-upbit_fee
                binance_profit=(df.at[Idx,'Price_sell_b']-df.at[Idx,'Price_buy_b'])*df.at[Idx,'Vol_sell_b']
                binance_fee=(df.at[Idx,'Price_sell_b']*df.at[Idx,'Vol_sell_b']+df.at[Idx,'Price_Buy_b']*df.at[Idx,'Vol_Buy_b'])*0.0004
                binance_net_profit=binance_profit-binance_fee
                binance_net_profit_coinfx=round(binance_net_profit*df.at[Idx,'Exe_xkp'],)
                final_profit=round(upbit_net_profit+binance_net_profit_coinfx,)
                
                await message.answer("거래번호:{}, {}코인 김프탈출거래 실행!\n 희망탈출김프:{}\n{}\n<거래실행정보>\n업비트매도가:{}, 업비트매도수량:{}\n바이낸스매수가:{}, 바이낸스매수수량:{}\n탈출김프:{}"
                .format(Idx,df.at[Idx,'Coin_ticker'],format(df.at[Idx,'Wish_xkp'],','), now,format(T_data2[0][0],','),format(T_data2[0][1],','),format(T_data2[1][0],','),format(T_data2[1][1],','),format(T_data2[2],',')))
                await message.answer("업비트 거래총손익:KRW {}\n바이낸스 거래총손익:USD {}\n바이낸스탈출김프기준 거래원화손익:KRW {}\n탈출김프기준 최종손익:KRW {}"
                .format(upbit_net_profit,binance_net_profit,format(binance_net_profit_coinfx,','),format(final_profit,',')))
                
                #<거래실행정보>\n업비트매도가:{}, 업비트매도수량:{}\n바이낸스매수가:{}, 바이낸스매수수량:{}\n진입김프:{}
                
                df.loc[Idx, ('Vol_sell_u', 'Vol_buy_b', 'Exe_xkp')] = ( T_data2[0][1], T_data2[1][1], T_data2[2])

            else:
                await message.answer("탈출대기중인 거래만 종료가능합니다")
        else:
            await message.answer("사용법 /execoin 거래번호\n거래번호는 한개씩만 입력가능합니다.")
    except Exception as e:
        await message.answer("execoin함수 오류발생{}".format(e))
        pass  


if __name__ == '__main__':
    #await asyncio.gather(executor.start_polling(dp, skip_updates=True),upbit_ws_client())
    executor.start_polling(dp, skip_updates=True)
    
