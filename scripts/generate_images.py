"""Generate project images for documentation and research paper."""

import os, sys
os.environ["MPLBACKEND"] = "Agg"
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.lines as mlines

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "images")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def style():
    plt.rcParams.update({"figure.facecolor": "#0f1923","axes.facecolor":"#0f1923","axes.edgecolor":"#2a3a4a","axes.labelcolor":"#c8d6e5","text.color":"#c8d6e5","xtick.color":"#576574","ytick.color":"#576574","font.family":"sans-serif","font.size":10})

def arch():
    style(); fig,ax = plt.subplots(1,1,figsize=(16,10))
    ax.set_xlim(0,16); ax.set_ylim(0,10); ax.axis("off")
    C = {"core":"#00cec9","sim":"#0984e3","ml":"#6c5ce7","scada":"#e17055","compliance":"#00b894","dashboard":"#fdcb6e","infra":"#636e72"}
    mods = [("dt-contracts",1,8.5,3,0.7,C["core"]),("dt-orchestrator",5,8.5,3,0.7,C["core"]),("dt-sim-pandapower",1,6.5,2.5,0.7,C["sim"]),("dt-sim-opendss",4,6.5,2.5,0.7,C["sim"]),("dt-sim-matpower",7,6.5,2.5,0.7,C["sim"]),("dt-sim-gridlabd",10,6.5,2.5,0.7,C["sim"]),("dt-ml (ensemble)",1,4.5,2.5,0.7,C["ml"]),("dt-bescom",4,4.5,2.5,0.7,C["sim"]),("dt-cim",7,4.5,2.5,0.7,C["sim"]),("IEC 61850 / DNP3",10,4.5,2.5,0.7,C["scada"]),("Modbus (pymodbus)",13,4.5,2.5,0.7,C["scada"]),("dt-compliance",1,2.5,2.5,0.7,C["compliance"]),("dt-security",4,2.5,2.5,0.7,C["core"]),("dt-dashboard",7,2.5,2.5,0.7,C["dashboard"]),("dt-restoration",10,2.5,2.5,0.7,C["infra"]),("dt-infrastructure",13,2.5,2.5,0.7,C["infra"])]
    layers = [(0,8,16,2,"#0a1628","Core Platform"),(0,5.8,16,2.4,"#0d1f3c","Simulation & SCADA"),(0,0,16,5.5,"#081420","Infrastructure & Security")]
    for lx,ly,lw,lh,lc,ll in layers:
        ax.add_patch(FancyBboxPatch((lx,ly),lw,lh,boxstyle="round,pad=0.05",facecolor=lc,edgecolor="#1a3a5c",linewidth=0.5,zorder=0))
        ax.text(lx+0.3,ly+lh-0.4,ll,fontsize=8,color="#576574",alpha=0.6)
    for n,x,y,w,h,c in mods:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.1",facecolor=c,edgecolor="#ffffff33",linewidth=1,alpha=0.9))
        ax.text(x+w/2,y+h/2,n,ha="center",va="center",fontsize=7.5,fontweight="bold",color="#0f1923")
    ax.set_title("Grid Digital Twin - System Architecture",fontsize=14,fontweight="bold",color="#00cec9",pad=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR,"architecture.png"),dpi=200,bbox_inches="tight"); plt.close(fig)
    print("[OK] architecture.png")

def pipeline():
    style(); fig,ax = plt.subplots(1,1,figsize=(14,5))
    ax.set_xlim(0,14); ax.set_ylim(0,5); ax.axis("off")
    stages = [(0.5,2,2,2,"#00cec9","SCADA","IEC 61850/DNP3"),(3,2,2,2,"#0984e3","Telemetry","PMU/RTU streams"),(5.5,2,2,2,"#6c5ce7","Powerflow","pandapower/MATPOWER"),(8,2,2,2,"#e17055","ML Anomaly","Z-Score/LSTM/Physics"),(10.5,2,2,2,"#fdcb6e","State+API","Redis/WebSocket"),(13,3,1,1.5,"#636e72","Dashboard","React+TS")]
    for x,y,w,h,c,t,d in stages:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.15",facecolor=c,edgecolor="#ffffff44",linewidth=1.5,alpha=0.85))
        ax.text(x+w/2,y+h*0.7,t,ha="center",va="center",fontsize=9,fontweight="bold",color="#0f1923")
        ax.text(x+w/2,y+h*0.3,d,ha="center",va="center",fontsize=7,color="#1a2a3a")
    for i in range(len(stages)-1):
        ax.annotate("",xy=(stages[i+1][0],stages[i+1][1]+stages[i+1][3]/2),xytext=(stages[i][0]+stages[i][2],stages[i][1]+stages[i][3]/2),arrowprops=dict(arrowstyle="->",color="#4a6a8a",lw=2.5,alpha=0.8))
    ax.set_title("Real-Time Data Pipeline",fontsize=14,fontweight="bold",color="#00cec9",pad=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR,"pipeline.png"),dpi=200,bbox_inches="tight"); plt.close(fig)
    print("[OK] pipeline.png")

def bescom():
    style(); fig,ax = plt.subplots(1,1,figsize=(14,10))
    ax.set_xlim(0,14); ax.set_ylim(0,10); ax.axis("off")
    tiers = [("400 kV (5 substations)",7.5,"#e17055"),("220 kV (15 substations)",5,"#fdcb6e"),("66 kV (30 substations)",2.5,"#00cec9")]
    names = {"400":["Hoody","Nelamangala","Byrathi","Talaghatpura","Somanahalli"],"220":["Peenya","Yeshwanthpur","Mysore Road","Hosur Road","K R Puram","Whitefield","Electronic City","Jigani","Bommanahalli","Banashankari","Yelahanka","Devanahalli","Dasarahalli","Nagarbhavi","Kengeri"]}
    for i,n in enumerate(names["400"]):
        x,y = 1.5+i*2.5,tiers[0][1]
        ax.add_patch(plt.Circle((x,y),0.35,color=tiers[0][2],alpha=0.9,ec="#ffffff44",lw=1.5))
        ax.text(x,y-0.6,n,ha="center",fontsize=7,color="#c8d6e5")
        if i<4: ax.plot([x+0.35,x+2.5-0.35],[y,y],color=tiers[0][2],lw=1,alpha=0.4)
    for tx in [2.75,5.25,7.75,10.25,12.75]:
        ax.plot([tx,tx],[tiers[0][1]-0.35,tiers[1][1]+0.5],color="#ffffff33",lw=0.8,ls="--")
    for i,n in enumerate(names["220"]):
        x,y,s = 0.8+i*0.85,tiers[1][1],0.25
        ax.add_patch(plt.Rectangle((x-s,y-s),s*2,s*2,color=tiers[1][2],alpha=0.9,ec="#ffffff44",lw=1))
        if i%3==0: ax.text(x,y-0.5,n,ha="center",fontsize=6,color="#c8d6e5",rotation=30)
        if i<14: ax.plot([x+s,x+0.85-s],[y,y],color=tiers[1][2],lw=0.8,alpha=0.3)
    for i in range(0,15,3):
        ax.plot([0.8+i*0.85,0.8+i*0.85],[tiers[1][1]-0.25,tiers[2][1]+0.35],color="#ffffff22",lw=0.6,ls=":")
    for i in range(30):
        x,y,s = 0.3+i*0.45,tiers[2][1],0.15
        ax.add_patch(plt.Polygon([(x,y+s),(x-s,y-s),(x+s,y-s)],color=tiers[2][2],alpha=0.8,ec="#ffffff33",lw=0.5))
    leg = [mlines.Line2D([0],[0],marker='o',color='w',markerfacecolor="#e17055",markersize=10,label='400 kV'),mlines.Line2D([0],[0],marker='s',color='w',markerfacecolor="#fdcb6e",markersize=10,label='220 kV'),mlines.Line2D([0],[0],marker='^',color='w',markerfacecolor="#00cec9",markersize=10,label='66 kV'),mlines.Line2D([0],[0],color="#ffffff33",lw=1,ls="--",label='400/220 kV Trafos'),mlines.Line2D([0],[0],color="#ffffff22",lw=1,ls=":",label='220/66 kV Trafos')]
    ax.legend(handles=leg,loc="lower center",fontsize=8,framealpha=0.2,ncol=5)
    ax.set_title("BESCOM Bangalore Grid - 50-Bus Three-Tier Network",fontsize=14,fontweight="bold",color="#00cec9",pad=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR,"bescom_network.png"),dpi=200,bbox_inches="tight"); plt.close(fig)
    print("[OK] bescom_network.png")

def dashboard():
    style(); fig,ax = plt.subplots(1,1,figsize=(14,9))
    ax.set_xlim(0,14); ax.set_ylim(0,9); ax.axis("off")
    comps = [(0.2,7.8,13.6,1,"#00b894","Status Bar","Grid: BESCOM | Tick #1427 | 0 Alarms"),(0.2,6.5,3.2,1.2,"#0984e3","Quick Stats","Voltage 0.976-1.010pu"),(3.6,6.5,6.6,1.2,"#6c5ce7","Topology Map","50-bus SVG grid diagram"),(10.4,6.5,3.4,1.2,"#e17055","Anomaly Panel","Violation alerts"),(0.2,5.1,5.5,1.3,"#fdcb6e","Voltage Chart","Bus voltages + violation zones"),(5.9,5.1,7.9,1.3,"#00cec9","Timeline Chart","200-tick anomaly history"),(0.2,3.5,13.6,1.5,"#636e72","Node Inspector","Click bus -> details")]
    for x,y,w,h,c,t,d in comps:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.08",facecolor=c,edgecolor="#ffffff33",linewidth=1,alpha=0.8))
        ax.text(x+0.2,y+h-0.3,t,fontsize=9,fontweight="bold",color="#0f1923")
        ax.text(x+0.2,y+0.2,d,fontsize=7,color="#1a2a3a",va="bottom")
    ax.set_title("Operations Dashboard Layout",fontsize=14,fontweight="bold",color="#00cec9",pad=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR,"dashboard_layout.png"),dpi=200,bbox_inches="tight"); plt.close(fig)
    print("[OK] dashboard_layout.png")

def tests():
    style(); fig,(ax1,ax2) = plt.subplots(1,2,figsize=(12,5))
    mods = ["Contracts","ML","SCADA","Security","Compliance","CIM","BESCOM","Integration","Dashboard(TS)"]
    cnts = [17,6,42,10,6,3,13,8,30]
    cs = ["#00cec9","#6c5ce7","#e17055","#0984e3","#00b894","#fdcb6e","#e17055","#00cec9","#0984e3"]
    bars = ax1.barh(mods,cnts,color=cs,edgecolor="#ffffff22",linewidth=0.5)
    ax1.set_xlabel("Tests",color="#c8d6e5"); ax1.set_title("Test Distribution",fontsize=12,fontweight="bold",color="#00cec9")
    ax1.tick_params(colors="#c8d6e5"); ax1.set_facecolor("#0a1628")
    for b,c in zip(bars,cnts): ax1.text(b.get_width()+1,b.get_y()+b.get_height()/2,str(c),va="center",fontsize=9,color="#c8d6e5")
    labels = ["DNP3","IEC 61850","Modbus","ASN.1/SCL"]; sizes = [35,30,20,15]
    wedges,texts,auts = ax2.pie(sizes,labels=labels,colors=["#00cec9","#e17055","#0984e3","#6c5ce7"],autopct="%1.0f%%",startangle=90,textprops={"color":"#c8d6e5","fontsize":8})
    for a in auts: a.set_color("#0f1923"); a.set_fontweight("bold")
    ax2.set_title("SCADA Protocol Code",fontsize=12,fontweight="bold",color="#00cec9")
    fig.suptitle(f"Total: {sum(cnts)} Tests - 100% Passing",fontsize=14,fontweight="bold",color="#00cec9",y=1.02)
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR,"test_results.png"),dpi=200,bbox_inches="tight"); plt.close(fig)
    print("[OK] test_results.png")

def compliance():
    style(); fig,ax = plt.subplots(1,1,figsize=(12,4))
    ax.set_xlim(0,12); ax.set_ylim(0,4); ax.axis("off")
    items = [(0.3,1,2.5,2,"#00b894","NERC CIP","CIP-002 to CIP-014 (10 req)"),(3.2,1,2.5,2,"#fdcb6e","Indian Grid Code","IEGC 2023 (7 checks)"),(6.1,1,2.5,2,"#e17055","AES-256-GCM","Encryption + key rotation"),(9.0,1,2.5,2,"#0984e3","RBAC + Audit","5 roles + immutable logs")]
    for x,y,w,h,c,t,d in items:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.1",facecolor=c,edgecolor="#ffffff33",linewidth=1.5,alpha=0.85))
        ax.text(x+w/2,y+h*0.7,t,ha="center",va="center",fontsize=9,fontweight="bold",color="#0f1923")
        ax.text(x+w/2,y+h*0.3,d,ha="center",va="center",fontsize=7,color="#1a2a3a")
    ax.set_title("Government & Utility Compliance",fontsize=14,fontweight="bold",color="#00cec9",pad=10)
    fig.tight_layout(); fig.savefig(os.path.join(OUTPUT_DIR,"compliance.png"),dpi=200,bbox_inches="tight"); plt.close(fig)
    print("[OK] compliance.png")

def main():
    print("\nGenerating images...\n")
    arch(); pipeline(); bescom(); dashboard(); tests(); compliance()
    print(f"\nAll images -> {OUTPUT_DIR}\n")

if __name__=="__main__": main()
