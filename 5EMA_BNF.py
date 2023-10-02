import os, json
import pandas as pd
import sys, time, datetime, threading, pyotp
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from kiteext import KiteExt

global gc, kite

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gc = gspread.authorize(credentials)

def Zerodha_login_enc():
    global kite, gc
    isConnected = 0
    try:
        kite = KiteExt()

        worksheet = gc.open('Zerodha_Login').sheet1

        UserID = worksheet.cell(2, 2).value.strip()
        enc = worksheet.cell(5, 2).value.strip()
        # Totp = worksheet.cell(4, 2).value.strip()

        # print(f"UserID={UserID},  Enc Token={enc}")

        # kite.login_with_credentials(userid=UserID, password=Password, secret=Totp)
        kite.login_using_enctoken(userid=UserID, enctoken=enc)

        Profile = kite.profile()
        # print(Profile)

        client_name = Profile.get('user_name')

        print('Login Successful, Welcome ' + client_name)
        isConnected = 1

    except Exception as e:
        print(f"Error : {e}")

    return isConnected

try:
    Zerodha_login_enc()

    instrument = 'BANKNIFTY'
    option_buy_or_sell = 'BUY'

    live_trading = False
    product_type = 'MIS'

    strick_atm_diff = -100
    lots_to_trade = 1
    expiry = 0

    max_sl_points = 30
    risk_reward = 3

    max_ce_trades = 3
    max_pe_trades = 3
    total_trades = 3

    entry_time_start = datetime.time(9, 15, 0)
    entry_time_stop = datetime.time(15, 0, 0)

    square_off_time = datetime.time(15, 10, 0)

    move_sl_to_cost = True
except:
    print("UserInput Issue!!!!!!")
    time.sleep(3)
    sys.exit()

print(f"Algo Start for {instrument}")

while True:
    try:
        df = pd.DataFrame(kite.instruments())
        break
    except Exception as e:
        time.sleep(1)

spot_df_main = df.copy()
spot_df_main = spot_df_main[
    (spot_df_main["exchange"] == "NSE") &
    (
        (spot_df_main["tradingsymbol"] == ("NIFTY 50" if instrument == "NIFTY" else
                                           ("NIFTY BANK" if instrument == "BANKNIFTY" else
                                            ("NIFTY FIN SERVICE" if instrument == "FINNIFTY" else "NIFTY MID SELECT")))))
    ]


spot_df_main = spot_df_main.set_index("instrument_token")
spot_df_main = spot_df_main[["tradingsymbol"]]
spot_df_main["5min_SingleCandleHigh"] = None
spot_df_main["5min_SingleCandleLow"] = None
spot_df_main["5min_SingleCandleTime"] = None
spot_df_main["15min_SingleCandleHigh"] = None
spot_df_main["15min_SingleCandleLow"] = None
spot_df_main["15min_SingleCandleTime"] = None
spot_df_main["LTP"] = None

def append_data_to_sheet2(data):
    global gc
    # Replace 'YourGoogleSheetName' with the name of your Google Sheet
    sheet_name = 'Zerodha_Login'

    # Open the Google Sheet
    worksheet = gc.open(sheet_name).worksheet('Sheet2')

    # Append the data to the sheet
    worksheet.append_rows(data)

    
def scan_chart_data():
    # print("Historical Thread Started ----")
    while datetime.datetime.now().time() <= entry_time_stop:
        time.sleep(1)
        if datetime.datetime.now().minute % 5 == 0 and datetime.datetime.now().second == 3:
            while True:
                try:
                    data = kite.historical_data(instrument_token=list(spot_df_main.index)[0],
                                                interval="5minute",
                                                from_date=datetime.datetime.now().date() - datetime.timedelta(days=5),
                                                to_date=datetime.datetime.now())
                    break
                except Exception as e:
                    time.sleep(0.5)

            df = pd.DataFrame(data)
            df["only_date"] = df["date"].apply(lambda x: x.date())
            df = df.set_index("date")
            diff_time_df = pd.DataFrame()
            diff_time_df["open"] = df["open"].resample("15min").first()
            diff_time_df["high"] = df["high"].resample("15min").max()
            diff_time_df["low"] = df["low"].resample("15min").min()
            diff_time_df["close"] = df["close"].resample("15min").last()
            diff_time_df["volume"] = df["volume"].resample("15min").sum()
            diff_time_df = diff_time_df.dropna()

            df["EMA"] = df["close"].ewm(span=5, adjust=False).mean()
            df = df[df["only_date"] == datetime.datetime.now().date()]
            df = df[:-1]
            if len(df) != 0:
                if list(df["low"]) [-1] > list(df["EMA"])[-1]:
                    spot_df_main.loc[list(spot_df_main.index)[0], "5min_SingleCandleHigh"] = list(df["high"])[-1]
                    spot_df_main.loc[list(spot_df_main.index)[0], "5min_SingleCandleLow"] = list(df["low"])[-1]
                    spot_df_main.loc[list(spot_df_main.index)[0], "5min_SingleCandleTime"] = list(df.index)[-1]
                else:
                    spot_df_main.loc[list(spot_df_main.index)[0], "5min_SingleCandleHigh"] = None
                    spot_df_main.loc[list(spot_df_main.index)[0], "5min_SingleCandleLow"] = None
                    spot_df_main.loc[list(spot_df_main.index)[0], "5min_SingleCandleTime"] = None

            if datetime.datetime.now().minute % 15 == 0:
                df = diff_time_df.copy()
                df["date"] = df.index
                df["only_date"] = df["date"].apply(lambda x: x.date())
                df["EMA"] = df["close"].ewm(span=5, adjust=False).mean()
                df = df[df["only_date"] == datetime.datetime.now().date()]
                df = df[:-1]
                if len(df) != 0:
                    if list(df["high"])[-1] < list(df["EMA"])[-1]:
                        spot_df_main.loc[list(spot_df_main.index)[0], "15min_SingleCandleHigh"] = list(df["high"])[-1]
                        spot_df_main.loc[list(spot_df_main.index)[0], "15min_SingleCandleLow"] = list(df["low"])[-1]
                        spot_df_main.loc[list(spot_df_main.index)[0], "15min_SingleCandleTime"] = list(df.index)[-1]
                    else:
                        spot_df_main.loc[list(spot_df_main.index)[0], "15min_SingleCandleHigh"] = None
                        spot_df_main.loc[list(spot_df_main.index)[0], "15min_SingleCandleLow"] = None
                        spot_df_main.loc[list(spot_df_main.index)[0], "15min_SingleCandleTime"] = None
            # print("Historical Data Updated ....", datetime.datetime.now().strftime('%H:%M:%S'))

threading.Thread(target=scan_chart_data, args=()).start()

trade_df = pd.DataFrame(columns=['spot_symbol', 'trade_symbol', 'spot_breakout', 'trade_direction', 'trade_qty',
                                 'status', 'spot_entry_price', "avoid_signal", 'spot_sl', 'spot_target',
                                 'spot_exit_price', 'entry_price', 'exit_price', 'entry_time', 'exit_time', 'pnl'])
while True:
    current_time = datetime.datetime.now().time()
    dummy_date = datetime.date(1, 1, 1)
    total_closed_trades = len(trade_df[trade_df['status'] == 'CLOSE'])
    close_time = datetime.datetime.combine(dummy_date, square_off_time)
    close_time += datetime.timedelta(minutes=5)

    if (current_time > close_time.time()) or (total_closed_trades == total_trades):
        break
    time.sleep(0.5)
    try:
        data = kite.ltp(["NSE:" + list(spot_df_main["tradingsymbol"]) [0]])["NSE:" + list(spot_df_main["tradingsymbol"])[0]]
        spot_df_main.loc[data["instrument_token"],"LTP"] = data["last_price"]
    except Exception as e:
        continue

    # PE BUY
    spot_df = spot_df_main.copy()
    if list(spot_df["5min_SingleCandleTime"])[0] is not None and \
            len(trade_df[(trade_df["trade_direction"] == ("BUY" if option_buy_or_sell == "BUY" else "SELL")) &
                         (trade_df["trade_symbol"].str[-2:] == ("PE" if option_buy_or_sell == "BUY" else "CE")) &
                         (trade_df["status"] == "OPEN")]) ==0 and \
            len(trade_df[(trade_df["avoid_signal"] == list(spot_df["5min_SingleCandleTime"])[0]) &
                         (trade_df["trade_direction"] == ("BUY" if option_buy_or_sell == "BUY" else "SELL")) &
                         (trade_df["trade_symbol"].str[-2:] == ("PE" if option_buy_or_sell == "BUY" else "CE"))]) == 0 and \
            len(trade_df[(trade_df["trade_symbol"].str[-2:] == ("PE" if option_buy_or_sell == "BUY" else "CE"))]) < \
            (max_pe_trades if option_buy_or_sell == "BUY" else max_ce_trades) and len(trade_df) < total_trades and \
            entry_time_start < datetime.datetime.now().time() <entry_time_stop:
        if list(spot_df["LTP"])[0] < list(spot_df["5min_SingleCandleLow"])[0]:
            opt_df = df.copy()
            opt_df = opt_df[
                (opt_df["exchange"] == "NFO") &
                (opt_df["name"] == ("NIFTY" if list(spot_df["tradingsymbol"])[0] == "NIFTY 50" else
                                    ("BANKNIFTY" if list(spot_df["tradingsymbol"])[0] == "NIFTY BANK" else
                                     ("FINNIFTY" if list(spot_df["tradingsymbol"])[0] == "NIFTY FIN SERVICE" else"MIDCPNIFTY")))) &
                (opt_df["instrument_type"] == ("PE" if option_buy_or_sell == "BUY" else "CE"))]
            opt_df = opt_df[opt_df["expiry"] == sorted(list(opt_df["expiry"].unique()))[expiry]]
            strike = float(list(opt_df["strike"])[min(range(len(list(opt_df["strike"]))),
                                                      key=lambda j: abs(list(opt_df["strike"])[j] -list(spot_df["LTP"])[0]))])
            opt_df = opt_df[opt_df["strike"] == (strike - strick_atm_diff if option_buy_or_sell == "BUY" else strike + strick_atm_diff)]
            lot_size = list(opt_df["lot_size"])[0]
            trade = {"spot_symbol" : list(spot_df["tradingsymbol"])[0],
                     "trade_symbol" : list(opt_df["tradingsymbol"])[0],
                     "spot_breakout" : "DOWN",
                     "trade_direction" : option_buy_or_sell,
                     "trade_qty" : lot_size*lots_to_trade,
                     "status":"OPEN",
                     "spot_entry_price" : list(spot_df["5min_SingleCandleLow"])[0],
                     "signal_candle" : list(spot_df["5min_SingleCandleTime"])[0],
                     "avoid_signal" : list(spot_df["5min_SingleCandleTime"])[0],
                     "spot_sl" : list(spot_df["5min_SingleCandleHigh"])[0]
                     if (list(spot_df["5min_SingleCandleHigh"])[0] - list(spot_df["5min_SingleCandleLow"])[0]) < max_sl_points
                     else list(spot_df["5min_SingleCandleHigh"])[0] + max_sl_points,
                     "spot_target" : round(list(spot_df["5min_SingleCandleLow"])[0] -
                                           ((list(spot_df["5min_SingleCandleHigh"])[0] - list(spot_df["5min_SingleCandleLow"])[0])
                                           if (list(spot_df["5min_SingleCandleHigh"])[0] - list(spot_df["5min_SingleCandleLow"])[0]) < max_sl_points
                                            else max_sl_points)* risk_reward, 2),
                     "spot_exit_price" : None,
                     "entry_price" : None,
                     "exit_price" : None,
                     "entry_time" : datetime.datetime.now().strftime('%H:%M:%S'),
                     "exit_time" : None,
                     "pnl" : None}

            if live_trading:
                try:
                    order_id = kite.place_order(variety=kite.VARIETY_REGULAR,
                                                exchange="NFO",
                                                tradingsymbol=trade["trade_symbol"],
                                                transaction_type=trade["trade_direction"],
                                                quantity=trade["trade_qty"],
                                                product=product_type,
                                                order_type=kite.ORDER_TYPE_MARKET)
                    time.sleep(1)
                    while True:
                        try:
                            orderbook = pd.DataFrame(kite.orders())
                            trade["entry_price"] = list(orderbook[orderbook["order_id"] == order_id]["average_price"])[0]
                            break
                        except Exception as e:
                            time.sleep(1)
                except Exception as e:
                    print("PlaceOrder Error: ", e, "...", datetime.datetime.now().strftime('%H:%M:%S'))
                    trade["entry_price"] = 0
            else:
                while True:
                    try:
                        trade["entry_price"] = kite.ltp("NFO:" +trade["trade_symbol"])["NFO:"+trade["trade_symbol"]]["last_price"]
                        break
                    except Exception as e:
                        time.sleep(1)

            print("Spot Ltp", list(spot_df["LTP"])[0], "...", datetime.datetime.now().strftime('%H:%M:%S'))
            print("Trade Opened", trade["trade_symbol"], trade["trade_direction"], "QTY", trade["trade_qty"],
                  "@ Price", trade["entry_price"], "...", datetime.datetime.now().strftime('%H:%M:%S'))
            print("Spot Entry: ",trade["spot_entry_price"],"Spot Stoploss: ",trade["spot_sl"],"Spot Target: ",trade["spot_target"])
            print("-----")
            trade_df = pd.concat([trade_df, pd.DataFrame({0: trade}).transpose()], ignore_index=True)

    if list(spot_df["15min_SingleCandleTime"])[0] is not None and \
            len(trade_df[(trade_df["trade_direction"] == ("BUY" if option_buy_or_sell == "BUY" else "SELL")) &
                         (trade_df["trade_symbol"].str[-2:] == ("CE" if option_buy_or_sell == "BUY" else "PE")) &
                         (trade_df["status"] == "OPEN")]) == 0 and \
            len(trade_df[(trade_df["avoid_signal"] == list(spot_df["15min_SingleCandleTime"])[0]) &
                         (trade_df["trade_direction"] == ("BUY" if option_buy_or_sell == "BUY" else "SELL")) &
                         (trade_df["trade_symbol"].str[-2:] == ("CE" if option_buy_or_sell == "BUY" else "PE"))]) == 0 and \
            len(trade_df[(trade_df["trade_symbol"].str[-2:] == ("CE" if option_buy_or_sell == "BUY" else "PE"))]) < \
            (max_ce_trades if option_buy_or_sell == "BUY" else max_pe_trades) and len(trade_df) < total_trades and \
            entry_time_start < datetime.datetime.now().time() < entry_time_stop:
        if list(spot_df["LTP"])[0] > list(spot_df["15min_SingleCandleHigh"])[0]:
            opt_df = df.copy()
            opt_df = opt_df[
                (opt_df["exchange"] == "NFO") &
                (opt_df["name"] == ("NIFTY" if list(spot_df["tradingsymbol"])[0] == "NIFTY 50" else
                                    ("BANKNIFTY" if list(spot_df["tradingsymbol"])[0] == "NIFTY BANK" else
                                     ("FINNIFTY" if list(spot_df["tradingsymbol"])[0] == "NIFTY FIN SERVICE" else "MIDCPNIFTY")))) &
                (opt_df["instrument_type"] == ("CE" if option_buy_or_sell == "BUY" else "PE"))]
            opt_df = opt_df[opt_df["expiry"] == sorted(list(opt_df["expiry"].unique()))[expiry]]
            strike = float(list(opt_df["strike"])[min(range(len(list(opt_df["strike"]))),
                                                      key= lambda j: abs(list(opt_df["strike"]) [j] - list(spot_df["LTP"])[0]))])
            opt_df = opt_df[opt_df["strike"] == (strike + strick_atm_diff if option_buy_or_sell == "BUY" else strike - strick_atm_diff)]
            lot_size = list(opt_df["lot_size"])[0]
            trade = {"spot_symbol": list(spot_df["tradingsymbol"])[0],
                     "trade_symbol": list(opt_df["tradingsymbol"])[0],
                     "spot_breakout": "UP",
                     "trade_direction": option_buy_or_sell,
                     "trade_qty": lot_size * lots_to_trade,
                     "status": "OPEN",
                     "spot_entry_price": list(spot_df["15min_SingleCandleHigh"])[0],
                     "signal_candle": list(spot_df["15min_SingleCandleTime"])[0],
                     "avoid_signal": list(spot_df["15min_SingleCandleTime"])[0],
                     "spot_sl": list(spot_df["15min_SingleCandleLow"])[0]
                     if (list(spot_df["15min_SingleCandleHigh"])[0] - list(spot_df["15min_SingleCandleLow"])[0]) < max_sl_points
                     else list(spot_df["15min_SingleCandleHigh"])[0] - max_sl_points,
                     "spot_target": round(list(spot_df["15min_SingleCandleHigh"])[0] +
                                          ((list(spot_df["15min_SingleCandleHigh"])[0] -list(spot_df["15min_SingleCandleLow"])[0])
                                           if (list(spot_df["15min_SingleCandleHigh"])[0] - list(spot_df["15min_SingleCandleLow"])[0]) < max_sl_points
                                           else max_sl_points) * risk_reward, 2),
                     "spot_exit_price": None,
                     "entry_price": None,
                     "exit_price": None,
                     "entry_time": datetime.datetime.now().strftime('%H:%M:%S'),
                     "exit_time": None,
                     "pnl": None}

            if live_trading:
                try:
                    order_id = kite.place_order(variety=kite.VARIETY_REGULAR,
                                                exchange="NFO",
                                                tradingsymbol=trade["trade_symbol"],
                                                transaction_type=trade["trade_direction"],
                                                quantity=trade["trade_qty"],
                                                product=product_type,
                                                order_type=kite.ORDER_TYPE_MARKET)
                    time.sleep(1)
                    while True:
                        try:
                            orderbook = pd.DataFrame(kite.orders())
                            trade["entry_price"] = list(orderbook[orderbook["order_id"] == order_id]["average_price"])[0]
                            break
                        except Exception as e:
                            time.sleep(1)
                except Exception as e:
                    print("PlaceOrder Error: ", e, "...", datetime.datetime.now().strftime('%H:%M:%S'))
                    trade["entry_price"] = 0
            else:
                while True:
                    try:
                        trade["entry_price"] = kite.ltp("NFO:" +trade["trade_symbol"])["NFO:"+trade["trade_symbol"]]["last_price"]
                        break
                    except Exception as e:
                        time.sleep(1)
            print("Spot Ltp", list(spot_df["LTP"])[0], "...", datetime.datetime.now().strftime('%H:%M:%S'))
            print("Trade Opened", trade["trade_symbol"], trade["trade_direction"], "QTY", trade["trade_qty"],
                  "@ Price", trade["entry_price"], "...", datetime.datetime.now().strftime('%H:%M:%S'))
            print("Spot Entry: ",trade["spot_entry_price"],"Spot Stoploss: ",trade["spot_sl"],"Spot Target: ",trade["spot_target"])
            print("-----")
            trade_df = pd.concat([trade_df, pd.DataFrame({0: trade}).transpose()], ignore_index=True)

    for i in trade_df.index:
        if trade_df["status"][i] == "OPEN":
            if trade_df["avoid_signal"][i] != list(spot_df["5min_SingleCandleTime"])[0] and \
                    trade_df["spot_breakout"][i] == "DOWN" and list(spot_df["5min_SingleCandleTime"])[0] is not None:
                trade_df.loc[i, "avoid_signal"] = list(spot_df["5min_SingleCandleTime"])[0]
                # print("Avoid 'Market Down' Signal Candle", trade_df["avoid_signal"][i].time())
            if trade_df["avoid_signal"][i] != list(spot_df["15min_SingleCandleTime"])[0] and \
                    trade_df["spot_breakout"][i] == "UP" and list(spot_df["15min_SingleCandleTime"])[0] is not None:
                trade_df.loc[i, "avoid_signal"] = list(spot_df["15min_SingleCandleTime"])[0]
                # print("Avoid 'Market UP' Signal Candle", trade_df["avoid_signal"][i].time())
            if trade_df["spot_entry_price"][i] != trade_df["spot_sl"][i] and \
                    list(spot_df["LTP"])[0] < trade_df["spot_entry_price"][i] - ((trade_df["spot_sl"][i] - trade_df["spot_entry_price"][i]) * risk_reward/2) and \
                    trade_df["spot_breakout"][i] == "DOWN":
                trade_df.loc[i,"spot_sl"] = trade_df["spot_entry_price"][i]
                print("Spot LTP", list(spot_df["LTP"])[0], "....", datetime.datetime.now().strftime('%H:%M:%S'))
                print("Spot Entry Price: ", trade_df["spot_entry_price"][i], "Spot SL: ", trade_df["spot_sl"][i], "Spot LTP: ", list(spot_df["LTP"])[0])
                print("Trade Update", trade_df["trade_symbol"][i], "Spot SL Trailed to Break-even", "...", datetime.datetime.now().strftime('%H:%M:%S'))
                print("-----")

            if trade_df["spot_entry_price"][i] != trade_df["spot_sl"][i] and \
                    list(spot_df["LTP"])[0] > trade_df["spot_entry_price"][i] + ((trade_df["spot_entry_price"][i] - trade_df["spot_sl"][i]) * risk_reward/2) and \
                    trade_df["spot_breakout"][i] == "UP":
                # CHanges to check where it gap while traling sl
                print("Data in Trade_df")
                print("Spot Entry : ", trade_df["spot_entry_price"][i], "Spot SL : ", trade_df.loc[i,"spot_sl"], "Target : ",trade_df["spot_target"][i])
                trade_df.loc[i,"spot_sl"] = trade_df["spot_entry_price"][i]
                print("Spot LTP", list(spot_df["LTP"])[0], "....", datetime.datetime.now().strftime('%H:%M:%S'))
                print("Trade Update", trade_df["trade_symbol"][i], "Spot SL Trailed to Break-even", "...", datetime.datetime.now().strftime('%H:%M:%S'))
                print("-----")

            if (list(spot_df["LTP"])[0] > trade_df["spot_sl"][i] if trade_df["spot_breakout"][i] == "DOWN" else list(spot_df["LTP"])[0] < trade_df["spot_sl"][i]) or \
                    (list(spot_df["LTP"])[0] < trade_df["spot_target"][i] if trade_df["spot_breakout"][i] == "DOWN"
                    else list(spot_df["LTP"])[0] > trade_df["spot_target"][i]) or datetime.datetime.now().time() > square_off_time:
                trade_df.loc[i, "status"] = "CLOSE"
                trade_df.loc[i, "exit_time"] = datetime.datetime.now().strftime('%H:%M:%S')
                trade_df.loc[i, "spot_exit_price"] = list(spot_df["LTP"])[0]
                if live_trading:
                    try:
                        if trade_df["entry_price"][i] == 0:
                            raise Exception("Entry Not Verified/Completed!!!!!")
                        order_id = kite.place_order(variety=kite.VARIETY_REGULAR,
                                                    exchange="NFO",
                                                    tradingsymbol=trade_df["trade_symbol"][i],
                                                    transaction_type="SELL" if trade_df["trade_direction"][i] == "BUY" else "BUY",
                                                    quantity=trade_df["trade_qty"][i],
                                                    product=product_type,
                                                    order_type=kite.ORDER_TYPE_MARKET)
                        time.sleep(1)
                        while True:
                            try:
                                orderbook = pd.DataFrame(kite.orders())
                                trade_df.loc[i, "exit_price"] = list(orderbook[orderbook["order_id"] == order_id]["average_price"])[0]
                                break
                            except Exception as e:
                                time.sleep(1)
                    except Exception as e:
                        print("PlaceOrder Error : ", e, "...", datetime.datetime.now().strftime('%H:%M:%S'))
                        trade_df.loc[i, "exit_price"] = 0
                else:
                    while True:
                        try:
                            trade_df.loc[i, "exit_price"] = kite.ltp("NFO:" + trade_df["trade_symbol"][i])["NFO:"+trade_df["trade_symbol"][i]]["last_price"]
                            break
                        except Exception as e:
                            time.sleep(1)
                if trade_df["trade_direction"][i] == "BUY":
                    pnl = (trade_df["exit_price"][i] - trade_df["entry_price"][i]) * trade_df["trade_qty"][i]
                else:
                    pnl = (trade_df["exit_price"][i] - trade_df["entry_price"][i]) * trade_df["trade_qty"][i]
                trade_df.loc[i, "pnl"] = pnl
                print("Spot Ltp", list(spot_df["LTP"])[0], "...", datetime.datetime.now().strftime('%H:%M:%S'))
                print("Trade Closed", trade_df["trade_symbol"][i], "@ Price", trade_df["exit_price"][i], "PnL", round(pnl, 2), "....", datetime.datetime.now().strftime('%H:%M:%S'))
                print("-----")

os.makedirs("Logs", exist_ok=True)

trade_df = trade_df.rename(columns={"trade_symbol" : "Symbol", "trade_direction" : "Direction", "trade_qty" : "Qty", "spot_entry_price": "SpotEntryPrice",
                                    "spot_exit_price":"SpotExitPrice", "entry_price": "EntryPrice", "exit_price" : "ExitPrice",
                                    "entry_time": "EntryTime", "exit_time" : "ExitTime", "pnl" : "PnL"})
trade_df = trade_df[['Symbol','Direction', 'Qty', 'SpotEntryPrice', 'SpotExitPrice', 'EntryPrice', 'EntryTime', 'ExitPrice', 'ExitTime', 'PnL']]
trade_df.to_csv(f"Logs/{instrument}_{datetime.datetime.now().date()}.csv")
trade_df = trade_df.astype(str)
trade_df.insert(0,"Date",datetime.datetime.now().strftime('%d-%B-%Y'))
data_to_append = trade_df.values.tolist()
append_data_to_sheet2(data_to_append)

print("-----Algo Stopped-----")
time.sleep(10)
sys.exit()

