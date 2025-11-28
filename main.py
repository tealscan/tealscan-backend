from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import casparser
import shutil
import os
from pyxirr import xirr
from datetime import date

app = FastAPI()

# Allow your React app to talk to this Python app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace * with your Vercel URL
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_asset_class(name):
    n = name.upper()
    if any(x in n for x in ["LIQUID", "DEBT", "BOND"]): return "Debt"
    if "GOLD" in n: return "Gold"
    return "Equity"

@app.get("/")
def home():
    return {"status": "TealScan Brain is Active"}

@app.post("/scan")
async def scan_portfolio(file: UploadFile = File(...), password: str = Form(...)):
    try:
        # Save file temporarily
        with open("temp.pdf", "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Parse PDF
        data = casparser.read_cas_pdf("temp.pdf", password, force_pdfminer=True)
        
        portfolio = []
        total_val = 0.0
        total_invested = 0.0
        commission_loss = 0.0
        
        for folio in data.folios:
            for scheme in folio.schemes:
                name = scheme.scheme
                val = float(scheme.valuation.value or 0)
                cost = float(scheme.valuation.cost or 0)
                
                if val < 100: continue
                
                is_regular = "DIRECT" not in name.upper()
                loss = val * 0.01 if is_regular else 0
                
                # XIRR Calculation
                dates, amts = [], []
                for txn in scheme.transactions:
                    amt = float(txn.amount or 0)
                    if amt == 0: continue
                    desc = str(txn.description).upper()
                    if any(x in desc for x in ["PURCHASE", "SIP"]): amts.append(amt * -1)
                    else: amts.append(amt)
                    dates.append(txn.date)
                
                dates.append(date.today())
                amts.append(val)
                
                try:
                    res = xirr(dates, amts)
                    my_xirr = res * 100 if res else 0
                except: my_xirr = 0
                
                portfolio.append({
                    "fund_name": name,
                    "category": get_asset_class(name),
                    "value": val,
                    "type": "Regular" if is_regular else "Direct",
                    "xirr": round(my_xirr, 2),
                    "loss": round(loss, 0)
                })
                
                total_val += val
                total_invested += cost
                commission_loss += loss
                
        # Clean up
        os.remove("temp.pdf")
        
        return {
            "status": "success",
            "summary": {
                "net_worth": total_val,
                "total_invested": total_invested,
                "total_gain": total_val - total_invested,
                "hidden_fees": commission_loss
            },
            "funds": portfolio
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
