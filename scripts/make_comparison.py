"""Compose unchanged real Qt captures with an explicitly labelled reference brief.

The inline reference screenshots are visible to the agent, but have no source
file IDs/bytes in the workspace. Do not fabricate or label a recreated screenshot
as the original. The left column is a textual visual brief, not a screenshot.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont


def compose(folder='docs'):
    folder=Path(folder)
    scan=Image.open(folder/'actual-scan.png').convert('RGB')
    browse=Image.open(folder/'actual-browse.png').convert('RGB')
    left=410;gap=24;top=96
    width=left+gap+max(scan.width,browse.width)+24
    height=top+scan.height+browse.height+130
    canvas=Image.new('RGB',(width,height),'#eef4fb');draw=ImageDraw.Draw(canvas)
    regular='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    if not Path(regular).exists():regular='C:/Windows/Fonts/arial.ttf';bold='C:/Windows/Fonts/arialbd.ttf'
    title=ImageFont.truetype(bold,27);heading=ImageFont.truetype(bold,20);font=ImageFont.truetype(regular,18)
    draw.text((22,18),'v0.2.0 – referenciák és tényleges alkalmazás',font=title,fill='#073e78')
    draw.text((22,55),'A jobb oldalon változatlan Qt-képernyőmentések, elkülönített szintetikus QA-adatokkal.',font=font,fill='#36516b')
    draw.rounded_rectangle((15,top, left-5,height-30),radius=8,fill='#dbeafa',outline='#7199c4',width=2)
    notes=[('REFERENCIA – VIZUÁLIS JEGYZET',['A csatolt képek alapján:','KDE 3 Keramik jelleg','Kék–ezüst, klasszikus asztali UI']),
           ('Panelrendszer',['Kék színátmenetes címsorok','Finom keret és fényes gombok','Három átméretezhető oszlop','Külön tallózó oldal']),
           ('Ikonrendszer',['Valódi Crystal Clear műveletek','KDE Crystal SVG PDF-ikon','32 px fő eszköztár','24 px gombok és fülek','20 px panel, 16 px lista/menü']),
           ('Működő felület',['Közös felső/alsó műveletek','Kék kijelölés, színes állapotok','Nagy PDF-megjelenítési terület','Alsó állapot- és oldalszámláló']),
           ('Forráskorlát',['Ez a bal oldali rész szöveges','referenciaösszefoglaló, nem az','eredeti képernyőterv másolata.','Az üzenetbe ágyazott képek','fájlbájtjai nem érhetők el a','munkatérben. A megvalósítás','azok látható tartalmára épült.'])]
    y=top+20
    for head,lines in notes:
        draw.text((30,y),head,font=heading,fill='#074d87');y+=34
        for line in lines:draw.text((30,y),line,font=font,fill='#203e5c');y+=28
        y+=25
    logo=Image.open('assets/branding/application.png').convert('RGBA');logo.thumbnail((270,270))
    canvas.paste(logo,(60,y),logo)
    draw.text((left+gap,top-30),'TÉNYLEGES: Szkennelések feldolgozása',font=heading,fill='#074d87')
    canvas.paste(scan,(left+gap,top))
    next_y=top+scan.height+65
    draw.text((left+gap,next_y-30),'TÉNYLEGES: Szerződések tallózása',font=heading,fill='#074d87')
    canvas.paste(browse,(left+gap,next_y))
    canvas.save(folder/'ui-comparison.png')


if __name__=='__main__':compose()
