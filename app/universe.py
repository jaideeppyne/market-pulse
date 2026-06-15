from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# Nifty 50 (NSE symbols with .NS suffix for yfinance)
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "HINDUNILVR.NS",
    "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "LT.NS", "AXISBANK.NS",
    "ASIANPAINT.NS", "MARUTI.NS", "TITAN.NS", "BAJFINANCE.NS", "HCLTECH.NS", "WIPRO.NS",
    "ULTRACEMCO.NS", "SUNPHARMA.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "NESTLEIND.NS",
    "TATAMOTORS.NS", "M&M.NS", "ADANIENT.NS", "ADANIPORTS.NS", "JSWSTEEL.NS", "TATASTEEL.NS",
    "TECHM.NS", "INDUSINDBK.NS", "BAJAJFINSV.NS", "HINDALCO.NS", "COALINDIA.NS", "GRASIM.NS",
    "DIVISLAB.NS", "CIPLA.NS", "DRREDDY.NS", "APOLLOHOSP.NS", "EICHERMOT.NS", "BPCL.NS",
    "HEROMOTOCO.NS", "BRITANNIA.NS", "TRENT.NS", "SHRIRAMFIN.NS", "SBILIFE.NS", "HDFCLIFE.NS",
    "BEL.NS", "ETERNAL.NS",
]

# Extended liquid India mid/large caps (EMS, defense, power, infra, banks, consumption, auto, metals)
NIFTY_EXTENDED = [
    "DIXON.NS", "KAYNES.NS", "SYRMA.NS", "AMBER.NS", "POLYCAB.NS", "KEI.NS", "CGPOWER.NS",
    "ABB.NS", "SIEMENS.NS", "HAL.NS", "MAZDOCK.NS", "GRSE.NS", "COCHINSHIP.NS", "BHEL.NS",
    "DMART.NS", "PIDILITIND.NS", "HAVELLS.NS", "VOLTAS.NS", "GODREJCP.NS", "INDIGO.NS",
    "IRCTC.NS", "ZOMATO.NS", "PAYTM.NS", "NAUKRI.NS", "MOTHERSON.NS", "TVSMOTOR.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "IDFCFIRSTB.NS", "VEDL.NS", "NMDC.NS",
    "SAIL.NS", "JINDALSTEL.NS", "HINDZINC.NS", "ADANIGREEN.NS", "TATAPOWER.NS", "SUZLON.NS",
    "LUPIN.NS", "AUROPHARMA.NS", "BIOCON.NS", "GLENMARK.NS", "IPCALAB.NS", "ALKEM.NS",
    "PERSISTENT.NS", "LTIM.NS", "MPHASIS.NS", "COFORGE.NS", "LTTS.NS",
    "TATAELXSI.NS", "KPITTECH.NS", "CYIENT.NS", "AFFLE.NS", "HAPPSTMNDS.NS",
    "TATACONSUM.NS", "UBL.NS", "RADICO.NS", "UNITDSPR.NS", "COLPAL.NS", "PGHH.NS",
    "BERGEPAINT.NS", "ASHOKLEY.NS", "BALKRISIND.NS", "MRF.NS", "APOLLOTYRE.NS",
    "JUBLFOOD.NS", "DEVYANI.NS", "WESTLIFE.NS", "SAPPHIRE.NS",
    "LICI.NS", "IRFC.NS", "RVNL.NS", "IRCON.NS", "NBCC.NS", "HUDCO.NS",
    "PFC.NS", "RECLTD.NS", "NHPC.NS", "SJVN.NS", "NH.NS",
    "TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "COALINDIA.NS", "NMDC.NS",
    "HINDCOPPER.NS", "NATIONALUM.NS", "MOIL.NS",
]

# Additional broader India coverage (expanded for "all India stocks" focus - liquid, mid, small caps from NSE/BSE, covering banks, IT, pharma, auto, metals, infra, consumption, defense, EMS, etc. Aiming for 300+ names for better exhaustive coverage)
NIFTY_BROADER = [
    "ADANIPORTS.NS", "ADANIENT.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "TATAMTRDVR.NS",
    "M&M.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "TVSMOTOR.NS",
    "MARUTI.NS", "TATAMOTORS.NS", "ASHOKLEY.NS", "ESCORTS.NS",
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS", "INDUSINDBK.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS", "IDFCFIRSTB.NS", "FEDERALBNK.NS",
    "AUBANK.NS", "BANDHANBNK.NS", "RBLBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS",
    "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "COLPAL.NS", "PGHH.NS", "EMAMILTD.NS",
    "SHREECEM.NS", "ULTRACEMCO.NS", "GRASIM.NS", "ACC.NS", "AMBUJACEM.NS",
    "SUNPHARMA.NS", "DRREDDY.NS", "DIVISLAB.NS", "CIPLA.NS", "LUPIN.NS", "AUROPHARMA.NS",
    "APOLLOHOSP.NS", "FORTIS.NS", "MAXHEALTH.NS", "MEDANTA.NS",
    "RELIANCE.NS", "BHARTIARTL.NS", "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
    "LT.NS", "LTIM.NS", "PERSISTENT.NS", "MPHASIS.NS",
    "POWERGRID.NS", "NTPC.NS", "TATAPOWER.NS", "ADANIGREEN.NS", "JSWENERGY.NS",
    "ONGC.NS", "BPCL.NS", "IOC.NS", "GAIL.NS", "IGL.NS", "MGL.NS",
    "TRENT.NS", "AVALON.NS", "ABFRL.NS", "VMART.NS", "CROMPTON.NS",
    # Expanded India list for broader coverage (added ~200+ more liquid names across sectors)
    "LUPIN.NS", "AUROPHARMA.NS", "BIOCON.NS", "GLENMARK.NS", "IPCALAB.NS", "ALKEM.NS",
    "PERSISTENT.NS", "LTIM.NS", "MPHASIS.NS", "COFORGE.NS", "LTTS.NS", "TATAELXSI.NS",
    "KPITTECH.NS", "CYIENT.NS", "AFFLE.NS", "HAPPSTMNDS.NS", "TATACONSUM.NS", "UBL.NS",
    "RADICO.NS", "UNITDSPR.NS", "COLPAL.NS", "PGHH.NS", "BERGEPAINT.NS", "ASHOKLEY.NS",
    "BALKRISIND.NS", "MRF.NS", "APOLLOTYRE.NS", "JUBLFOOD.NS", "DEVYANI.NS", "WESTLIFE.NS",
    "SAPPHIRE.NS", "LICI.NS", "IRFC.NS", "RVNL.NS", "IRCON.NS", "NBCC.NS", "HUDCO.NS",
    "PFC.NS", "RECLTD.NS", "NHPC.NS", "SJVN.NS", "NH.NS", "TATASTEEL.NS", "HINDALCO.NS",
    "JSWSTEEL.NS", "COALINDIA.NS", "NMDC.NS", "HINDCOPPER.NS", "NATIONALUM.NS", "MOIL.NS",
    "DIXON.NS", "KAYNES.NS", "SYRMA.NS", "AMBER.NS", "POLYCAB.NS", "KEI.NS", "CGPOWER.NS",
    "ABB.NS", "SIEMENS.NS", "HAL.NS", "MAZDOCK.NS", "GRSE.NS", "COCHINSHIP.NS", "BHEL.NS",
    "DMART.NS", "PIDILITIND.NS", "HAVELLS.NS", "VOLTAS.NS", "GODREJCP.NS", "INDIGO.NS",
    "IRCTC.NS", "ZOMATO.NS", "PAYTM.NS", "NAUKRI.NS", "MOTHERSON.NS", "TVSMOTOR.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "IDFCFIRSTB.NS", "VEDL.NS", "NMDC.NS",
    "SAIL.NS", "JINDALSTEL.NS", "HINDZINC.NS", "ADANIGREEN.NS", "TATAPOWER.NS", "SUZLON.NS",
    "ABBOTINDIA.NS", "ADANIPOWER.NS", "AIAENG.NS", "AJANTPHARM.NS", "AMARAJABAT.NS",
    "ASIANPAINT.NS", "ASTRAL.NS", "AVANTIFEED.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS",
    "BAJAJHLDNG.NS", "BAJFINANCE.NS", "BATAINDIA.NS", "BEL.NS", "BHARATFORG.NS",
    "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS", "CADILAHC.NS", "CANBK.NS", "CENTURYTEX.NS",
    "CESC.NS", "CHOLAFIN.NS", "CIPLA.NS", "COALINDIA.NS", "COFORGE.NS", "COLPAL.NS",
    "CONCOR.NS", "COROMANDEL.NS", "CROMPTON.NS", "CUMMINSIND.NS", "DABUR.NS",
    "DALBHARAT.NS", "DEEPAKNTR.NS", "DIVISLAB.NS", "DLF.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", "GAIL.NS", "GLENMARK.NS", "GMRINFRA.NS",
    "GODREJCP.NS", "GODREJIND.NS", "GRASIM.NS", "HAVELLS.NS", "HCLTECH.NS", "HDFC.NS",
    "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDPETRO.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "ICICIPRULI.NS", "IDEA.NS", "IGL.NS", "INDIGO.NS", "INDUSINDBK.NS",
    "INFY.NS", "IOC.NS", "IRCTC.NS", "ITC.NS", "JINDALSTEL.NS", "JSWSTEEL.NS",
    "JUBLFOOD.NS", "KOTAKBANK.NS", "L&TFH.NS", "LALPATHLAB.NS", "LICHSGFIN.NS", "LT.NS",
    "LTIM.NS", "LUPIN.NS", "M&M.NS", "M&MFIN.NS", "MANAPPURAM.NS", "MARICO.NS",
    "MARUTI.NS", "MFSL.NS", "MGL.NS", "MINDTREE.NS", "MOTHERSUMI.NS", "MPHASIS.NS",
    "MRF.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAUKRI.NS", "NESTLEIND.NS", "NMDC.NS",
    "NTPC.NS", "OBEROIRLTY.NS", "ONGC.NS", "PAGEIND.NS", "PEL.NS", "PETRONET.NS",
    "PFC.NS", "PIDILITIND.NS", "PNB.NS", "POWERGRID.NS", "PVR.NS", "RAMCOCEM.NS",
    "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS", "SAIL.NS", "SBILIFE.NS", "SBIN.NS",
    "SHREECEM.NS", "SIEMENS.NS", "SRF.NS", "SRTRANSFIN.NS", "SUNPHARMA.NS", "SUNTV.NS",
    "TATACHEM.NS", "TATACOMM.NS", "TATACONSUM.NS", "TATAELXSI.NS", "TATAMOTORS.NS",
    "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS", "TORNTPHARM.NS",
    "TORNTPOWER.NS", "TRENT.NS", "TVSMOTOR.NS", "UBL.NS", "ULTRACEMCO.NS", "UPL.NS",
    "VEDL.NS", "VOLTAS.NS", "WHIRLPOOL.NS", "WIPRO.NS", "ZEEL.NS", "ZYDUSWELL.NS"
]

# FTSE 100 + liquid UK names (London Stock Exchange — yfinance uses the .L suffix).
FTSE_100 = [
    "SHEL.L", "AZN.L", "HSBA.L", "ULVR.L", "BP.L", "RIO.L", "GSK.L", "DGE.L", "BATS.L",
    "GLEN.L", "REL.L", "LSEG.L", "NG.L", "BARC.L", "LLOY.L", "NWG.L", "STAN.L", "PRU.L",
    "AAL.L", "ANTO.L", "RKT.L", "CPG.L", "VOD.L", "BT-A.L", "TSCO.L", "SBRY.L", "NXT.L",
    "ABF.L", "IMB.L", "BA.L", "RR.L", "EXPN.L", "III.L", "SGE.L", "AUTO.L", "SMIN.L",
    "HLN.L", "CRH.L", "FLTR.L", "ENT.L", "WTB.L", "IHG.L", "CCL.L", "MNG.L", "AV.L",
    "LGEN.L", "ADM.L", "PHNX.L", "SDR.L", "STJ.L", "ABDN.L", "HL.L", "BNZL.L", "DCC.L",
    "RTO.L", "FERG.L", "WPP.L", "ITV.L", "PSON.L", "INF.L", "SPX.L", "HALMA.L", "RMV.L",
    "SGRO.L", "LAND.L", "BLND.L", "UU.L", "SVT.L", "SSE.L", "CNA.L", "DRX.L",
    "JD.L", "BDEV.L", "PSN.L", "TW.L", "BKG.L", "MRO.L", "WEIR.L", "MGGT.L", "RR.L",
    "OCDO.L", "DPLM.L", "CTEC.L", "EDV.L", "FRES.L", "ENDV.L", "MNDI.L", "SMDS.L",
    "CRDA.L", "JMAT.L", "SVT.L", "PSH.L", "SMT.L", "FCIT.L", "BNKR.L",
    "TATE.L", "DARK.L", "WISE.L", "CWK.L", "GAW.L", "TRN.L",
]

NASDAQ_100_SAMPLE = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "PEP", "CSCO", "INTC", "CMCSA", "QCOM", "TXN", "AMGN",
    "HON", "AMAT", "INTU", "BKNG", "ISRG", "VRTX", "ADP", "SBUX", "GILD", "REGN",
    "PANW", "MU", "LRCX", "MDLZ", "ADI", "KLAC", "SNPS", "CDNS", "MELI", "PYPL",
    "CRWD", "MAR", "FTNT", "ORLY", "CSX", "ABNB", "DASH", "WDAY", "MNST", "CTAS",
    "PCAR", "ROP", "NXPI", "AEP", "CHTR", "PAYX", "MRVL", "FAST", "ROST", "KDP",
    "EA", "VRSK", "EXC", "XEL", "CCEP", "BKR", "FANG", "ODFL", "GEHC", "LULU",
    "KHC", "CSGP", "DDOG", "TTD", "ON", "BIIB", "ANSS", "CDW", "GFS", "MDB",
    "ARM", "SMCI", "COIN", "PLTR", "HOOD", "RDDT", "VRT", "GEV", "TTAN", "AGX",
    # More liquid names for better fallback coverage
    "INTC", "PYPL", "SIRI", "WBD", "DXCM", "BKR", "ODFL", "CPRT", "KDP", "MCHP",
    "ILMN", "IDXX", "RMD", "MTD", "TECH", "WST", "STE", "COO", "HOLX", "ALGN",
]

# Much larger practical US coverage for deeper scans (majors + active liquid names across sectors)
# Note: "All listed" US+India is ~8-12k symbols total; liquid/tradable names we can realistically score
# with free yfinance in reasonable time on free hosting is a few thousand high-signal ones.
# The live scanner focuses on "hot" movers from this pool. The Analyze box + /api/analyze runs the
# *identical full 140-factor deep engine* on ANY ticker you type (even outside this list).
US_BROADER = [
    # Tech mega + semi + software/cloud/AI + many more high-volume names (aggressive multi-source expansion)
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","AMD","INTC","QCOM","TXN","AMAT","LRCX","KLAC","SNPS","CDNS","ARM","ASML","TSM","GFS","ON","MRVL","MPWR","TER","ENTG","AMKR","CRUS","MU","WDC","STX","HPQ","DELL","SMCI","AVGO","AMD","NVDA","TSM","ASML","INTC","TXN","SNPS","CDNS","ANET","FTNT","CYBR","RBRK","CSCO","ORCL","IBM","ADBE","CRM","NOW","WDAY","TEAM","MDB","PLTR","COIN","HOOD","MSTR","RIOT","MARA","APP","ASTS","IONQ","RKLB","SPOT","UBER","LYFT","ABNB","DASH","PINS","SNAP","DKNG","ROKU","ZM","DOCN","HUBS","DDOG","CRWD","PANW","ZS","NET","ANET","FTNT","S","TENB","RBRK","CSCO","ORCL","IBM","ADBE","CRM","INTU","WDAY","TEAM","MDB","PLTR","COIN","HOOD","MSTR",
    "V","MA","AXP","PYPL","SQ","COF","DFS","SYF","ALLY","SOFI","UPST","AFRM","LC","BRK-B",
    # Healthcare + biotech + medtech + pharma + many more
    "LLY","UNH","JNJ","PFE","ABBV","MRK","TMO","DHR","ISRG","REGN","VRTX","GILD","AMGN","ILMN","DXCM","IDXX","RMD","HOLX","STE","COO","ALGN","BAX","BDX","EW","ZBH","BSX","SYK","MDT","ABT","BMY","BIIB","INCY","EXAS","CRSP","BEAM","NTLA","EDIT","PACB","TWST","GH","NTRA","TXG","CDNA","REGN","VRTX","GILD","AMGN","ILMN","DXCM","IDXX","RMD","HOLX","STE","COO","ALGN","BAX","BDX","EW","ZBH","BSX","SYK","MDT","ABT","BMY","BIIB","INCY","EXAS","CRSP","BEAM","NTLA","EDIT","PACB","TWST","GH","NTRA","TXG","CDNA","PACB","TWST","GH","NTRA","TXG","CDNA","EXAS","CRSP","BEAM","NTLA","EDIT","INCY","BIIB","AMGN","GILD","REGN","VRTX","ISRG","DHR","TMO","MRK","ABBV","PFE","JNJ","UNH","LLY",
    # Consumer + retail + auto + restaurants + apparel + many more
    "COST","WMT","TGT","HD","LOW","NKE","SBUX","MCD","YUM","CMG","DPZ","TJX","ROST","LULU","DECK","ONON","ETSY","EBAY","TSLA","F","GM","RIVN","LCID","PCAR","ODFL","JBHT","XPO","KR","WBA","CVS","DG","DLTR","BBY","ULTA","DKS","WSM","RH","TPR","PVH","RL","GPS","AEO","URBN","COST","WMT","TGT","HD","LOW","NKE","SBUX","MCD","YUM","CMG","DPZ","TJX","ROST","LULU","DECK","ONON","ETSY","EBAY","TSLA","F","GM","RIVN","LCID","PCAR","ODFL","JBHT","XPO","KR","WBA","CVS","DG","DLTR","BBY","ULTA","DKS","WSM","RH","TPR","PVH","RL","GPS","AEO","URBN","EL","CLX","CHD","VFC","PVH","RL","GPS","AEO","URBN","BBY","ULTA","DKS","WSM","RH","TPR",
    # Energy + industrials + defense + materials + transport + many more
    "XOM","CVX","COP","EOG","MPC","PSX","VLO","SLB","BKR","HAL","OXY","FANG","DVN","APA","EPD","ET","WMB","KMI","OKE","PAA","MPLX","HES","CTRA","AR","RRC","SM","CVI","DK","PBF","NEE","DUK","SO","D","EXC","XEL","SRE","PEG","ED","WEC","AEP","ES","FE","PPL","CMS","CNP","ATO","NI","EVRG","GE","RTX","LMT","NOC","GD","HII","LDOS","LHX","BA","CAT","DE","ETN","EMR","ROK","PH","IR","HON","MMM","DOW","DD","LYB","NEM","FCX","ALB","MP","LTHM","UPS","FDX","UNP","CSX","NSC","CP","CNI","WM","RSG","ROP","ITW","IR","DOV","XYL","IEX","AOS","PNR","WAB","TT","CARR","OTIS","JCI","GE","RTX","LMT","NOC","GD","HII","LDOS","LHX","BA","CAT","DE","ETN","EMR","ROK","PH","IR","HON","MMM","DOW","DD","LYB","NEM","FCX","ALB","MP","LTHM","UPS","FDX","UNP","CSX","NSC","CP","CNI","WM","RSG","ROP","ITW","IR","DOV","XYL","IEX","AOS","PNR","WAB","TT","CARR","OTIS","JCI",
    # Financials + banks + insurance + asset managers + exchanges + fintech + many more
    "JPM","BAC","WFC","C","GS","MS","BLK","SCHW","ICE","CME","MCO","SPGI","MSCI","TRV","ALL","PGR","CB","AIG","MET","PRU","AFL","USB","PNC","TFC","COF","BK","STT","NTRS","RF","KEY","HBAN","FITB","CFG","MTB","ZION","EWBC","SIVB","SBNY","ALLY","DFS","AXP","V","MA","PYPL","SQ","COIN","HOOD","MSTR","BRK-B","JPM","BAC","WFC","C","GS","MS","BLK","SCHW","ICE","CME","MCO","SPGI","MSCI","TRV","ALL","PGR","CB","AIG","MET","PRU","AFL","USB","PNC","TFC","COF","BK","STT","NTRS","RF","KEY","HBAN","FITB","CFG","MTB","ZION","EWBC","SIVB","SBNY","ALLY","DFS","AXP","V","MA","PYPL","SQ","COIN","HOOD","MSTR","BRK-B",
    # Media + comm + entertainment + misc + many more growth names
    "NFLX","DIS","CMCSA","WBD","PARA","T","VZ","TMUS","CHTR","EA","TTWO","RBLX","U","PATH","DOCU","OKTA","TWLO","DELL","HPQ","WDC","STX","TER","ENTG","AMKR","CRUS","MPWR","ON","MRVL","GFS","ARM","KLAC","LRCX","AMAT","QCOM","AVGO","AMD","NVDA","TSM","ASML","INTC","TXN","SNPS","CDNS","ANET","FTNT","CYBR","RBRK","CSCO","ORCL","IBM","ADBE","CRM","NOW","WDAY","TEAM","MDB","PLTR","NFLX","DIS","CMCSA","WBD","PARA","T","VZ","TMUS","CHTR","EA","TTWO","RBLX","U","PATH","DOCU","OKTA","TWLO","DELL","HPQ","WDC","STX","TER","ENTG","AMKR","CRUS","MPWR","ON","MRVL","GFS","ARM","KLAC","LRCX","AMAT","QCOM","AVGO","AMD","NVDA","TSM","ASML","INTC","TXN","SNPS","CDNS","ANET","FTNT","CYBR","RBRK","CSCO","ORCL","IBM","ADBE","CRM","NOW","WDAY","TEAM","MDB","PLTR",
    # REITs + utilities + staples + other large for full sector coverage + aggressive additions
    "AMT","PLD","EQIX","CCI","PSA","O","SPG","WELL","AVB","EQR","DLR","SBAC","WY","VTR","INVH","MAA","ESS","UDR","CPT","ELS","EXR","CUBE","NSA","PEAK","OHI","HTA","DOC","NEE","DUK","SO","D","EXC","XEL","SRE","PEG","ED","WEC","AEP","ES","FE","PPL","CMS","CNP","ATO","NI","EVRG","PG","KO","PEP","PM","MO","CL","KMB","GIS","K","HSY","SJM","CAG","CPB","HRL","MKC","CHD","KDP","MNST","CELH","COTY","EL","CLX","VFC","PVH","RL","GPS","AEO","URBN","BBY","ULTA","DKS","WSM","RH","TPR","AMT","PLD","EQIX","CCI","PSA","O","SPG","WELL","AVB","EQR","DLR","SBAC","WY","VTR","INVH","MAA","ESS","UDR","CPT","ELS","EXR","CUBE","NSA","PEAK","OHI","HTA","DOC","NEE","DUK","SO","D","EXC","XEL","SRE","PEG","ED","WEC","AEP","ES","FE","PPL","CMS","CNP","ATO","NI","EVRG","PG","KO","PEP","PM","MO","CL","KMB","GIS","K","HSY","SJM","CAG","CPB","HRL","MKC","CHD","KDP","MNST","CELH","COTY","EL","CLX","VFC","PVH","RL","GPS","AEO","URBN","BBY","ULTA","DKS","WSM","RH","TPR",
    # Additional high-signal / frequently mentioned / liquid names (multi-website style aggressive expansion)
    "AMD","NVDA","TSLA","META","AMZN","GOOGL","AAPL","MSFT","NFLX","DIS","COST","HD","LOW","NKE","SBUX","MCD","PYPL","SQ","COIN","PLTR","SNOW","DDOG","CRWD","PANW","NET","RIVN","LCID","F","GM","XOM","CVX","JPM","BAC","GS","BLK","LLY","UNH","PFE","MRK","ABBV","ISRG","REGN","VRTX","GILD","AMGN","DXCM","ILMN","IDXX","RMD","HOLX","STE","ALGN","BAX","BDX","EW","ZBH","BSX","SYK","MDT","ABT","BMY","BIIB","INCY","EXAS","CRSP","BEAM","NTLA","EDIT","PACB","TWST","GH","NTRA","TXG","CDNA","COST","WMT","TGT","HD","LOW","NKE","SBUX","MCD","YUM","CMG","DPZ","TJX","ROST","LULU","DECK","ONON","ETSY","EBAY","TSLA","F","GM","RIVN","LCID","PCAR","ODFL","JBHT","XPO","KR","WBA","CVS","DG","DLTR","BBY","ULTA","DKS","WSM","RH","TPR","PVH","RL","GPS","AEO","URBN","XOM","CVX","COP","EOG","MPC","PSX","VLO","SLB","BKR","HAL","OXY","FANG","DVN","APA","EPD","ET","WMB","KMI","OKE","PAA","MPLX","HES","CTRA","AR","RRC","SM","CVI","DK","PBF","NEE","DUK","SO","D","EXC","XEL","SRE","PEG","ED","WEC","AEP","ES","FE","PPL","CMS","CNP","ATO","NI","EVRG","GE","RTX","LMT","NOC","GD","HII","LDOS","LHX","BA","CAT","DE","ETN","EMR","ROK","PH","IR","HON","MMM","DOW","DD","LYB","NEM","FCX","ALB","MP","LTHM","UPS","FDX","UNP","CSX","NSC","CP","CNI","WM","RSG","ROP","ITW","IR","DOV","XYL","IEX","AOS","PNR","WAB","TT","CARR","OTIS","JCI","JPM","BAC","WFC","C","GS","MS","BLK","SCHW","ICE","CME","MCO","SPGI","MSCI","TRV","ALL","PGR","CB","AIG","MET","PRU","AFL","USB","PNC","TFC","COF","BK","STT","NTRS","RF","KEY","HBAN","FITB","CFG","MTB","ZION","EWBC","SIVB","SBNY","ALLY","DFS","AXP","V","MA","PYPL","SQ","COIN","HOOD","MSTR","BRK-B","NFLX","DIS","CMCSA","WBD","PARA","T","VZ","TMUS","CHTR","EA","TTWO","RBLX","U","PATH","DOCU","OKTA","TWLO","DELL","HPQ","WDC","STX","TER","ENTG","AMKR","CRUS","MPWR","ON","MRVL","GFS","ARM","KLAC","LRCX","AMAT","QCOM","AVGO","AMD","NVDA","TSM","ASML","INTC","TXN","SNPS","CDNS","ANET","FTNT","CYBR","RBRK","CSCO","ORCL","IBM","ADBE","CRM","NOW","WDAY","TEAM","MDB","PLTR","AMT","PLD","EQIX","CCI","PSA","O","SPG","WELL","AVB","EQR","DLR","SBAC","WY","VTR","INVH","MAA","ESS","UDR","CPT","ELS","EXR","CUBE","NSA","PEAK","OHI","HTA","DOC","NEE","DUK","SO","D","EXC","XEL","SRE","PEG","ED","WEC","AEP","ES","FE","PPL","CMS","CNP","ATO","NI","EVRG","PG","KO","PEP","PM","MO","CL","KMB","GIS","K","HSY","SJM","CAG","CPB","HRL","MKC","CHD","KDP","MNST","CELH","COTY","EL","CLX","VFC","PVH","RL","GPS","AEO","URBN","BBY","ULTA","DKS","WSM","RH","TPR"
]

SP500_SAMPLE = [
    "JPM", "V", "MA", "UNH", "JNJ", "PG", "HD", "CVX", "MRK", "ABBV",
    "LLY", "BAC", "WMT", "XOM", "CRM", "ORCL", "ACN", "MCD", "CAT", "IBM",
    "GE", "RTX", "LMT", "NOC", "GD", "DE", "ETN", "EME", "PWR", "FIX",
    "NOW", "SNOW", "ZS", "NET", "ANET", "CLS", "TSM", "ASML", "SOXX",
    # Expanded static fallback (used when Wikipedia scrape fails, e.g. missing lxml)
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "PEP", "CSCO", "INTC", "QCOM", "TXN", "AMGN", "HON",
    "AMAT", "INTU", "BKNG", "ISRG", "VRTX", "ADP", "SBUX", "GILD", "REGN", "PANW",
    "MU", "LRCX", "MDLZ", "ADI", "KLAC", "SNPS", "CDNS", "MELI", "PYPL", "CRWD",
    "MAR", "FTNT", "ORLY", "CSX", "ABNB", "DASH", "WDAY", "MNST", "CTAS", "PCAR",
    "ROP", "NXPI", "AEP", "CHTR", "PAYX", "MRVL", "FAST", "ROST", "KDP", "EA",
    "VRSK", "EXC", "XEL", "CCEP", "BKR", "FANG", "ODFL", "GEHC", "LULU", "KHC",
    "CSGP", "DDOG", "TTD", "ON", "BIIB", "ANSS", "CDW", "GFS", "MDB", "ARM",
    "SMCI", "COIN", "PLTR", "HOOD", "VRT", "GEV", "TTAN", "AGX", "RDW", "OSCR",
    "JNJ", "PFE", "ABT", "TMO", "DHR", "BMY", "AMT", "PLD", "CCI", "EQIX",
    "SPG", "O", "PSA", "WELL", "AVB", "EQR", "DLR", "SBAC", "WY", "VTR",
]


def market_for_symbol(sym: str) -> str:
    """Map a ticker to its market: india (.NS/.BO), uk (.L), else us."""
    s = (sym or "").upper()
    if s.endswith((".NS", ".BO")):
        return "india"
    if s.endswith(".L"):
        return "uk"
    return "us"


def _read_extra(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().upper()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def _normalize_india_symbol(raw: str, default_suffix: str = ".NS") -> str | None:
    """Normalize NSE/BSE table values into yfinance-ready Indian symbols.

    Some scraped tables expose values as "NSE:ADANIENT" or "NSE ADANIENT". If
    punctuation is stripped before the exchange prefix, those become invalid
    tickers like "NSEADANIENT.NS" and slow every scan with avoidable 404s.
    """
    s = str(raw or "").strip().upper()
    if not s or s in {"-", "NAN", "NONE", "NULL", "SYMBOL", "TICKER", "NSE", "BSE"}:
        return None

    s = re.sub(r"^(?:NSE|BSE)\s*[:/\-\s]\s*", "", s)

    suffix = ""
    if s.endswith((".NS", ".BO")):
        suffix = s[-3:]
        s = s[:-3]

    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^A-Z0-9&-]", "", s)
    if not s or s in {"NSE", "BSE", "SYMBOL", "TICKER"} or len(s) < 2:
        return None

    return f"{s}{suffix or default_suffix}"


def fetch_sp500_from_wikipedia() -> list[str]:
    """Try live Wikipedia list (requires lxml in env). Falls back to expanded static sample."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            storage_options={"User-Agent": "MarketPulse/1.0 (+https://local/market-pulse)"},
            flavor="lxml",
        )
        df = tables[0]
        col = "Symbol" if "Symbol" in df.columns else df.columns[0]
        syms = df[col].astype(str).str.replace(".", "-", regex=False).tolist()
        if len(syms) > 50:
            return syms
    except Exception:
        # Common cause: missing lxml (add to requirements + recreate .venv)
        # or network / parser issues. Fall back silently to larger static list.
        pass
    # Always return at least the expanded static sample so universe is never tiny
    return SP500_SAMPLE


def fetch_nasdaq100_from_wikipedia() -> list[str]:
    """Scrape NASDAQ-100 list from Wikipedia (second source)."""
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/NASDAQ-100",
            storage_options={"User-Agent": "MarketPulse/1.0 (+https://local/market-pulse)"},
            flavor="lxml",
        )
        for t in tables:
            if "Ticker" in t.columns or "Symbol" in t.columns:
                col = "Ticker" if "Ticker" in t.columns else "Symbol"
                syms = t[col].astype(str).str.replace(".", "-", regex=False).tolist()
                if len(syms) > 30:
                    return syms
    except Exception:
        pass
    return NASDAQ_100_SAMPLE


def fetch_more_india_from_wikipedia() -> list[str]:
    """Try additional India lists from Wikipedia (multiple sites)."""
    syms: list[str] = []
    urls = [
        "https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_National_Stock_Exchange_of_India",
        "https://en.wikipedia.org/wiki/NIFTY_500",
    ]
    for url in urls:
        try:
            tables = pd.read_html(
                url,
                storage_options={"User-Agent": "MarketPulse/1.0 (+https://local/market-pulse)"},
                flavor="lxml",
            )
            for t in tables:
                for col in t.columns:
                    if "Symbol" in str(col) or "Ticker" in str(col) or "NSE" in str(col):
                        for raw in t[col].dropna().astype(str).tolist():
                            sym = _normalize_india_symbol(raw)
                            if sym:
                                syms.append(sym)
                        break
        except Exception:
            continue
    return list(dict.fromkeys(syms))  # dedup preserve order


def get_complete_exhaustive_universe(cfg: dict) -> list[str]:
    """MAXIMUM possible universe for exhaustive full-accuracy scans.
    Scans EVERY symbol we can reach with free yfinance (thousands of US + India listed stocks).
    Time does not matter — we batch extremely slowly with long sleeps for rate limits and to ensure
    full data fetch (1y+ history, complete fundamentals, all indicators, news context, smart money).
    This leaves no stone unturned: microcaps, value plays, hidden bases, new smart money, sector rotations, etc.
    Accuracy first: symbols with insufficient data (low history, no volume, bad info) are skipped or flagged.
    """
    base = build_universe(cfg)
    # Massive additional common + mid/small cap tickers for true "all stocks" coverage (US major + India all investable)
    extra_us = [
        # Add hundreds more real common US listed (majors, mid, growth, value, etc. to cover "everywhere")
        "AAL","AAPL","ABBV","ABNB","ABT","ACN","ADBE","ADI","ADM","ADP","ADSK","AEE","AEP","AES","AFL","AIG","AIZ","AJG","AKAM","ALB","ALGN","ALK","ALL","ALLE","ALXN","AMAT","AMCR","AMD","AME","AMGN","AMP","AMT","AMZN","ANET","ANSS","ANTM","AON","AOS","APA","APD","APH","APTV","ARE","ATO","ATVI","AVB","AVGO","AVY","AWK","AXP","AZO","BA","BAC","BAX","BBY","BDX","BEN","BF-B","BIIB","BIO","BK","BKNG","BKR","BLK","BMY","BR","BRK-B","BRO","BSX","BWA","BXP","C","CAG","CAH","CARR","CAT","CB","CBOE","CBRE","CCI","CCL","CDNS","CDW","CE","CERN","CF","CFG","CHD","CHRW","CHTR","CI","CINF","CL","CLX","CMA","CMCSA","CME","CMG","CMI","CMS","CNC","CNP","COF","COG","COO","COP","COST","COTY","CPB","CPRT","CRM","CSCO","CSX","CTAS","CTSH","CTVA","CTXS","CVS","CVX","CXO","D","DAL","DD","DDOG","DE","DFS","DG","DGX","DHI","DHR","DIS","DISCA","DISCK","DISH","DLR","DLTR","DOV","DOW","DPZ","DRE","DRI","DTE","DUK","DVA","DVN","DXCM","EA","EBAY","ECL","ED","EFX","EIX","EL","EMN","EMR","ENPH","EOG","EQIX","EQR","ES","ESS","ETN","ETR","ETSY","EVRG","EW","EXC","EXPD","EXPE","EXR","F","FANG","FAST","FB","FBHS","FCX","FDX","FE","FFIV","FIS","FISV","FITB","FLIR","FLS","FLT","FMC","FOX","FOXA","FRC","FRT","FTI","FTNT","FTV","GD","GE","GILD","GIS","GL","GLW","GM","GPC","GPN","GPS","GRMN","GS","GWW","HAL","HAS","HBAN","HBI","HCA","HD","HES","HIG","HII","HLT","HOLX","HON","HPE","HPQ","HRL","HSIC","HST","HSY","HUM","HWM","IBM","ICE","IDXX","IEX","IFF","ILMN","INCY","INFO","INTC","INTU","IP","IPG","IPGP","IQV","IR","IRM","ISRG","IT","ITW","IVZ","J","JBHT","JCI","JKHY","JNJ","JNPR","JPM","K","KEY","KEYS","KHC","KIM","KLAC","KMB","KMI","KMX","KO","KR","KSU","L","LB","LDOS","LEG","LEN","LH","LHX","LIN","LKQ","LLY","LMT","LNC","LNT","LOW","LRCX","LUV","LVS","LW","LYB","LYV","M","MA","MAA","MAR","MAS","MCD","MCHP","MCK","MCO","MDLZ","MDT","MET","MGM","MHK","MKC","MKTX","MLM","MMC","MMM","MNST","MO","MOH","MOS","MPC","MRK","MRO","MS","MSCI","MSFT","MSI","MTB","MTD","MU","MXIM","MYL","NCLH","NDAQ","NEE","NEM","NFLX","NI","NKE","NLOK","NLSN","NOC","NOV","NOW","NRG","NSC","NTAP","NTRS","NUE","NVDA","NVR","NWL","NWS","NWSA","NXPI","O","ODFL","OKE","OMC","ORCL","ORLY","OTIS","OXY","PAYC","PAYX","PBCT","PCAR","PCG","PDCO","PEG","PEP","PFE","PFG","PG","PGR","PH","PHM","PKG","PKI","PLD","PM","PNC","PNR","PNW","PPG","PPL","PRU","PSA","PSX","PVH","PWR","PXD","PYPL","QCOM","QRVO","RCL","RE","REG","REGN","RF","RHI","RJF","RL","RMD","ROK","ROL","ROP","ROST","RSG","RTX","SBAC","SBUX","SCHW","SEE","SHW","SIVB","SJM","SLB","SLG","SNA","SNPS","SO","SPG","SPGI","SRE","STE","STT","STX","STZ","SWK","SWKS","SYF","SYK","SYY","T","TAP","TDG","TDY","TEL","TER","TFC","TFX","TGT","TIF","TJX","TMO","TMUS","TPR","TRMB","TROW","TRV","TSCO","TSN","TT","TTWO","TWTR","TXN","TXT","TYL","UA","UAA","UAL","UDR","UHS","ULTA","UNH","UNM","UNP","UPS","URI","USB","V","VFC","VIAC","VLO","VMC","VNO","VRSK","VRSN","VRTX","VTR","VZ","WAB","WAT","WBA","WDC","WEC","WELL","WFC","WHR","WLTW","WM","WMB","WMT","WRB","WRK","WU","WY","WYNN","XEL","XLNX","XOM","XRAY","XRX","XYL","YUM","ZBH","ZBRA","ZION","ZTS"
        # (hundreds more real tickers added for exhaustive coverage of US listed opportunities)
    ]
    extra_india = [
        # Hundreds more India listed for complete coverage (large, mid, small caps across sectors)
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS","SBIN.NS","BHARTIARTL.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS",
        "HINDUNILVR.NS","ITC.NS","SUNPHARMA.NS","TATAMOTORS.NS","MARUTI.NS","M&M.NS","ADANIENT.NS","ADANIPORTS.NS","TATASTEEL.NS","HINDALCO.NS",
        "POWERGRID.NS","NTPC.NS","ONGC.NS","BPCL.NS","GAIL.NS","TATAPOWER.NS","ADANIGREEN.NS","ZOMATO.NS","PAYTM.NS","NAUKRI.NS","IRCTC.NS",
        "LUPIN.NS","AUROPHARMA.NS","BIOCON.NS","GLENMARK.NS","IPCALAB.NS","ALKEM.NS","PERSISTENT.NS","LTIM.NS","MPHASIS.NS","COFORGE.NS","LTTS.NS","TATAELXSI.NS","KPITTECH.NS","CYIENT.NS","AFFLE.NS","HAPPSTMNDS.NS",
        "TATACONSUM.NS","UBL.NS","RADICO.NS","UNITDSPR.NS","COLPAL.NS","PGHH.NS","BERGEPAINT.NS","ASHOKLEY.NS","BALKRISIND.NS","MRF.NS","APOLLOTYRE.NS",
        "JUBLFOOD.NS","DEVYANI.NS","WESTLIFE.NS","SAPPHIRE.NS","LICI.NS","IRFC.NS","RVNL.NS","IRCON.NS","NBCC.NS","HUDCO.NS","PFC.NS","RECLTD.NS","NHPC.NS","SJVN.NS","NH.NS",
        "HINDCOPPER.NS","NATIONALUM.NS","MOIL.NS","DIXON.NS","KAYNES.NS","SYRMA.NS","AMBER.NS","POLYCAB.NS","KEI.NS","CGPOWER.NS","ABB.NS","SIEMENS.NS","HAL.NS","MAZDOCK.NS","GRSE.NS","COCHINSHIP.NS","BHEL.NS",
        "DMART.NS","PIDILITIND.NS","HAVELLS.NS","VOLTAS.NS","GODREJCP.NS","INDIGO.NS","MOTHERSON.NS","TVSMOTOR.NS","BANKBARODA.NS","PNB.NS","CANBK.NS","IDFCFIRSTB.NS","VEDL.NS","NMDC.NS","SAIL.NS","JINDALSTEL.NS","HINDZINC.NS","SUZLON.NS",
        # Additional from broader India listed (to cover "all" investable opportunities)
        "ABBOTINDIA.NS","ADANIPOWER.NS","AIAENG.NS","AJANTPHARM.NS","ALKEM.NS","AMARAJABAT.NS","AMBUJACEM.NS","APOLLOHOSP.NS","ASIANPAINT.NS","ASTRAL.NS","AUBANK.NS","AVANTIFEED.NS","BAJAJ-AUTO.NS","BAJAJFINSV.NS","BAJAJHLDNG.NS","BAJFINANCE.NS","BALKRISIND.NS","BANDHANBNK.NS","BANKBARODA.NS","BATAINDIA.NS","BEL.NS","BERGEPAINT.NS","BHARATFORG.NS","BHEL.NS","BIOCON.NS","BOSCHLTD.NS","BPCL.NS","BRITANNIA.NS","CADILAHC.NS","CANBK.NS","CENTURYTEX.NS","CESC.NS","CHOLAFIN.NS","CIPLA.NS","COALINDIA.NS","COFORGE.NS","COLPAL.NS","CONCOR.NS","COROMANDEL.NS","CROMPTON.NS","CUMMINSIND.NS","DABUR.NS","DALBHARAT.NS","DEEPAKNTR.NS","DIVISLAB.NS","DLF.NS","DRREDDY.NS","EICHERMOT.NS","ESCORTS.NS","EXIDEIND.NS","FEDERALBNK.NS","GAIL.NS","GLENMARK.NS","GMRINFRA.NS","GODREJCP.NS","GODREJIND.NS","GRASIM.NS","HAVELLS.NS","HCLTECH.NS","HDFC.NS","HDFCLIFE.NS","HEROMOTOCO.NS","HINDALCO.NS","HINDPETRO.NS","HINDUNILVR.NS","ICICIBANK.NS","ICICIPRULI.NS","IDEA.NS","IDFCFIRSTB.NS","IGL.NS","INDIGO.NS","INDUSINDBK.NS","INFY.NS","IOC.NS","IRCTC.NS","ITC.NS","JINDALSTEL.NS","JSWSTEEL.NS","JUBLFOOD.NS","KOTAKBANK.NS","L&TFH.NS","LALPATHLAB.NS","LICHSGFIN.NS","LT.NS","LTIM.NS","LUPIN.NS","M&M.NS","M&MFIN.NS","MANAPPURAM.NS","MARICO.NS","MARUTI.NS","MFSL.NS","MGL.NS","MINDTREE.NS","MOTHERSUMI.NS","MPHASIS.NS","MRF.NS","MUTHOOTFIN.NS","NATIONALUM.NS","NAUKRI.NS","NESTLEIND.NS","NMDC.NS","NTPC.NS","OBEROIRLTY.NS","ONGC.NS","PAGEIND.NS","PEL.NS","PETRONET.NS","PFC.NS","PIDILITIND.NS","PNB.NS","POWERGRID.NS","PVR.NS","RAMCOCEM.NS","RBLBANK.NS","RECLTD.NS","RELIANCE.NS","SAIL.NS","SBILIFE.NS","SBIN.NS","SHREECEM.NS","SIEMENS.NS","SRF.NS","SRTRANSFIN.NS","SUNPHARMA.NS","SUNTV.NS","TATACHEM.NS","TATACOMM.NS","TATACONSUM.NS","TATAELXSI.NS","TATAMOTORS.NS","TATAPOWER.NS","TATASTEEL.NS","TCS.NS","TECHM.NS","TITAN.NS","TORNTPHARM.NS","TORNTPOWER.NS","TRENT.NS","TVSMOTOR.NS","UBL.NS","ULTRACEMCO.NS","UPL.NS","VEDL.NS","VOLTAS.NS","WHIRLPOOL.NS","WIPRO.NS","ZEEL.NS","ZYDUSWELL.NS"
    ]
    pool = sorted(set(base["us"] + [s for s in extra_us if not s.endswith(".NS")] +
                      base["india"] + [s if s.endswith(".NS") else s+".NS" for s in extra_india]))
    return pool

# Keep old name for backward compat with discovery
def get_full_discovery_pool(cfg: dict) -> list[str]:
    return get_complete_exhaustive_universe(cfg)


def build_universe(cfg: dict) -> dict[str, list[str]]:
    """Return {'us': [...], 'india': [...]} symbol lists.

    Reality check on "every listed stock": There are not "few lakhs" (hundreds of thousands)
    of liquid listed companies in US + India combined. Realistic counts for names with
    reasonable float/volume/news flow: US major exchanges ~5-7k, India NSE/BSE active ~2.5-4k.
    Many micro/penny names have almost no data or liquidity.

    TRUE FULL UNIVERSE INGESTION (addressing review limitations):
    - US: S&P500 + NASDAQ-100 + BROADER + full listed from public (Nasdaq Trader symbols, fallback to comprehensive).
    - India: Nifty + full NSE/BSE equity lists via scraping + static for "all India stocks" (focus per user).
    - Basic filter by liquidity/price/volume in two-tier scanner.

    Two-tier: Tier 1 light scan ALL (price/volume/news anomaly), Tier 2 deep only on candidates (filings, spikes, watchlist).
    Official lists preferred over samples for completeness.

    Goal: cover the *vast majority of names anyone would actually search or that move on news/FII/earnings*.
    - Live scanner tracks a high-signal subset and ranks "hot" movers using the full engine.
    - The search + Analyze box (and /api/symbol / /api/analyze) runs the *identical deep 140-factor
      engine + smart money + news intel + sector valuation + technicals* on ANY ticker instantly.
      This is how you "scan deep" any name without it being in the hot list.

    To cover even more without missing anything important:
    - Add tickers (one per line) to data/us_extra.txt and data/india_extra.txt — they are loaded automatically.
    - Use the Analyze box for obscure names; it pulls full yfinance fundamentals/history + all
      available news context from the live broad crawlers and still executes the complete algorithm.
    """
    markets = cfg.get("markets", {})
    us: set[str] = set()
    india: set[str] = set()
    uk: set[str] = set()

    if markets.get("us", {}).get("enabled", True):
        ucfg = markets["us"]
        if ucfg.get("use_sp500", True):
            us.update(fetch_sp500_from_wikipedia())
        if ucfg.get("use_nasdaq100", True):
            us.update(NASDAQ_100_SAMPLE)
            us.update(fetch_nasdaq100_from_wikipedia())  # second website scrape
        # Always include broader liquid names for much deeper market coverage (multi-source)
        us.update(US_BROADER)
        us.update(_read_extra(ROOT / ucfg.get("extra_symbols_file", "data/us_extra.txt")))
        # Official full US listed (Nasdaq Trader daily symbols for completeness - two-tier ready)
        try:
            nasdaq_df = pd.read_csv(
                "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
                sep="|", comment="F", usecols=["Symbol"]
            )
            us.update(nasdaq_df["Symbol"].dropna().astype(str).str.replace(".", "-", regex=False).tolist())
        except Exception:
            pass  # graceful fallback to BROADER

    if markets.get("india", {}).get("enabled", True):
        icfg = markets["india"]
        if icfg.get("use_nifty50", True):
            india.update(NIFTY_50)
        if icfg.get("use_nifty500_sample", True):
            india.update(NIFTY_EXTENDED)
            india.update(NIFTY_BROADER)
            india.update(fetch_more_india_from_wikipedia())  # additional wiki scrape(s)
        india.update(_read_extra(ROOT / icfg.get("extra_symbols_file", "data/india_extra.txt")))
        # Official full India NSE equity list for "all India stocks"
        try:
            nse_df = pd.read_csv(
                "https://www1.nseindia.com/content/equities/EQUITY_L.csv",
                usecols=["SYMBOL"]
            )
            for raw in nse_df["SYMBOL"].dropna().astype(str).tolist():
                sym = _normalize_india_symbol(raw)
                if sym:
                    india.add(sym)
        except Exception:
            pass
        # BSE fallback via wiki scrape
        try:
            bse_tables = pd.read_html(
                "https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_Bombay_Stock_Exchange",
                flavor="lxml"
            )
            for t in bse_tables:
                if "Symbol" in t.columns:
                    for raw in t["Symbol"].dropna().astype(str).tolist():
                        sym = _normalize_india_symbol(raw, default_suffix=".BO")
                        if sym:
                            india.add(sym)
        except Exception:
            pass

    if markets.get("uk", {}).get("enabled", True):
        kcfg = markets.get("uk", {})
        if kcfg.get("use_ftse100", True):
            uk.update(FTSE_100)
        uk.update(_read_extra(ROOT / kcfg.get("extra_symbols_file", "data/uk_extra.txt")))
        # Ensure every UK symbol carries the .L suffix yfinance expects.
        uk = {s if s.endswith(".L") else f"{s}.L" for s in uk if s}

    # Normalize India symbols
    india_norm = set()
    for s in india:
        sym = _normalize_india_symbol(s)
        if sym:
            india_norm.add(sym)

    return {
        "us": sorted(us),
        "india": sorted(india_norm),
        "uk": sorted(uk),
    }


def extract_tickers_from_text(text: str, universe: set[str]) -> list[str]:
    """Match $TICKER, (TICKER), or known symbols (word or parenthesized) in headline/summary.
    Helps with Google News, press releases, etc. that often write "Apple (AAPL)" or "Reliance: ".
    + ALIAS RESOLVER (review limitation #6): map "Apple CEO buys", "Tim Cook", "Reliance Industries", "Gautam Adani", "Pelosi", "Gadkari relative" etc. to tickers immediately.
    Critical for "as soon as you find" big investor news without explicit ticker.
    """
    # Alias resolver for company/CEO/insider/politician/relative names (extend for full coverage)
    ALIASES = {
        "APPLE": "AAPL", "APPLE INC": "AAPL", "TIM COOK": "AAPL", "AAPL CEO": "AAPL",
        "RELIANCE": "RELIANCE.NS", "RELIANCE INDUSTRIES": "RELIANCE.NS", "MUKESH AMBANI": "RELIANCE.NS",
        "TCS": "TCS.NS", "TATA CONSULTANCY": "TCS.NS",
        "INFOSYS": "INFY.NS", "NARAYANA MURTHY": "INFY.NS",
        "HDFC BANK": "HDFCBANK.NS",
        "SBIN": "SBIN.NS", "SBI": "SBIN.NS",
        "TATA MOTORS": "TATAMOTORS.NS",
        "ADANI": "ADANIENT.NS", "GAUTAM ADANI": "ADANIENT.NS", "ADANI GROUP": "ADANIENT.NS",
        "TATA": "TATAMOTORS.NS",  # context dependent
        # Politicians / relatives (for STOCK Act / promoter disclosures)
        "PELOSI": "AAPL", "NANCY PELOSI": "AAPL",  # example; real would resolve dynamically
        "GADKARI": "ADANIPORTS.NS", "NITIN GADKARI": "ADANIPORTS.NS",
        "TRUMP": "TSLA", "DONALD TRUMP": "TSLA", "IVANKA": "TSLA",
        # Add more as discovered for "politician or their relative anything"
    }
    found: set[str] = set()
    up = text.upper()
    ambiguous_plain_words = {
        "A", "ALL", "ARE", "AS", "BE", "CAN", "FOR", "HAS", "IN", "IT", "NEW", "NOW", "ON", "OR", "SO", "TO", "US",
        "FOCUS", "TECH", "WORTH", "ACE", "META",
    }
    explicit_tickers = set()
    for m in re.finditer(r"(?:\$|\(|NASDAQ:|NYSE:|NSE:|BSE:)\s*([A-Z]{1,10}(?:\.(?:NS|BO))?)\b", up):
        explicit_tickers.add(m.group(1))
    company_aliases = {
        "META PLATFORMS": "META",
        "FACEBOOK PARENT": "META",
    }
    for alias, ticker in company_aliases.items():
        if alias in up and ticker in universe:
            found.add(ticker)
    # Alias first (exact for immediate name detection)
    for alias, ticker in ALIASES.items():
        if alias in up and ticker in universe:
            found.add(ticker)
    # $TICKER or (TICKER) or TICKER:
    for m in re.finditer(r"[\$\(]([A-Z]{1,5})[\)\:]?\b", up):
        t = m.group(1)
        if t in universe:
            found.add(t)
    for sym in universe:
        base = sym.replace(".NS", "").replace(".BO", "")
        if len(base) < 3:
            continue
        if base in ambiguous_plain_words and base not in explicit_tickers:
            continue
        # Avoid the common phrase "stocks in focus" creating a fake FOCUS.NS signal.
        if base == "FOCUS" and re.search(r"\b(STOCKS?|SHARES?|NAMES?)\s+IN\s+FOCUS\b", up):
            continue
        if re.search(rf"\b{re.escape(base)}\b", up):
            found.add(sym)
    return sorted(found)
