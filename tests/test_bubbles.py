# 泡泡字詞 完整測試：python3 tests/test_bubbles.py
import http.server, threading, os, sys, functools, time, re
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCC = os.environ.get('OCC_JS', '/tmp/claude-0/-home-claude/9a17a2fb-5839-5fe9-8d90-c2c107720ad9/scratchpad/occ/package/dist/umd/full.js')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
H = functools.partial(Q, directory=ROOT)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{PORT}/index.html'
res = []
def check(name, cond, info=''):
    res.append((name, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + name + (' ' + str(info) if (not cond and info) else ''))

def route(ctx):
    def occ(r): r.fulfill(path=OCC, content_type='application/javascript')
    ctx.route('**/opencc-js@1.0.5/dist/umd/full.js', occ)
    ctx.route('**/gstatic.com/**', lambda r: r.abort())

CAPKEEP=[False]
def teacher_login(p):
    if p.locator('[data-a=teacher]').count(): p.click('[data-a=teacher]')
    p.wait_for_selector('#field, #loginBtn')
    if p.locator('#loginBtn').count():
        p.click('#loginBtn')
    p.wait_for_selector('#field')

def apply_words(p, text):
    if p.is_hidden('#panel'): p.click('[data-a=panel]')
    p.fill('#wordsIn', text); p.click('[data-a=apply]')
    p.wait_for_function('window.__bb.D.words.length>0')
    if p.evaluate('window.__bb.D.set.cap') and not CAPKEEP[0]:
        p.select_option('#capSel', '0')

def ids(p): return p.evaluate('window.__bb.D.words.map(w=>w.id)')
def pop_by_id(p, i):
    p.evaluate(f"document.querySelector('.bub[data-id=\"{i}\"]').dispatchEvent(new PointerEvent('pointerdown',{{bubbles:true}}))")

with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = br.new_context(viewport={'width': 1100, 'height': 800}); route(ctx)
    errs = []
    t = ctx.new_page(); t.on('pageerror', lambda e: errs.append(str(e)))
    t.goto(BASE + '?local=1')
    check('首頁有老師與加入', t.is_visible('[data-a=teacher]') and t.is_visible('#joinIn'))
    # 首頁簡體切換 + 台灣用字
    t.click('[data-a=lang]'); check('首頁切簡體', '我是老师' in t.inner_text('body')); t.click('[data-a=lang]')
    check('首頁切回繁體', '我是老師' in t.inner_text('body'))
    # 登入畫面（本機模擬 Google 登入）
    d = ctx.new_page(); d.goto(BASE + '?local=1&deny=1'); d.click('[data-a=teacher]'); d.wait_for_selector('#loginBtn'); d.click('#loginBtn'); d.wait_for_timeout(300)
    check('非授權帳號被擋並顯示訊息', '不是授權' in d.inner_text('#pwErr') and not d.locator('#field').count())
    d.close()
    t.click('[data-a=teacher]'); t.wait_for_selector('#loginBtn')
    check('老師入口顯示 Google 登入', '請用老師的 Google' in t.inner_text('body'))
    teacher_login(t)
    check('進入老師後台', t.is_visible('#ctl'))
    # 解析
    r = t.evaluate("window.__bb.parseWords('你好 謝謝 老師\\npor favor, hola, gracias\\n你好=hola')")
    check('解析：中文空白、西文逗號、配對', len(r) == 7 and r[6]['tr'] == ['hola'] and r[3]['k'] == 'lat', r)
    r2 = t.evaluate("window.__bb.parseWords('你好=buenos días 謝謝=gracias 學生 朋友')")
    check('解析：配對翻譯含空白、混合單字', len(r2) == 4 and r2[0]['tr'] == ['buenos días'] and r2[2]['tr'] is None, r2)
    apply_words(t, '你好 謝謝 老師\npor favor, hola\n你好=hello')
    check('套用字詞', t.evaluate('window.__bb.D.words.length') == 6)
    t.wait_for_function("window.__bb.D.words.filter(w=>w.k=='zh').every(w=>w.py)", timeout=15000)
    check('自動拼音', t.evaluate("window.__bb.D.words[0].py").strip() != '')
    check('自動注音', t.evaluate("window.__bb.D.words[0].zy").strip() != '')
    # 簡體轉換
    apply_words(t, '謝謝 學習')
    check('簡繁雙存', t.evaluate("window.__bb.D.words[0].sc") == '谢谢')
    t.click('[data-a=script][data-v=sc]'); t.click('[data-a=start]')
    t.wait_for_selector('.bub')
    check('簡體顯示（台灣用字介面）', '设定' in t.inner_text('#bar') and '谢谢' in t.inner_text('#field'))
    t.click('#bar [data-a=script][data-v=tc]'); t.wait_for_timeout(200)
    check('切回繁體', '謝謝' in t.inner_text('#field'))
    # 注音/拼音/不標
    for a, ok in (('zy', lambda s: re.search('[ㄅ-ㄩ]', s)), ('py', lambda s: re.search('[a-zāáǎàēéěèīíǐìōóǒòūúǔù]', s)), ('none', lambda s: not s.strip())):
        if t.is_hidden('#panel'): t.click('[data-a=panel]')
        t.click(f'[data-a=ann][data-v={a}]'); t.wait_for_timeout(150)
        txt = t.evaluate("[...document.querySelectorAll('.bub .ba')].map(e=>e.textContent).join('')")
        check('標示 ' + a, ok(txt) is not None if a != 'none' else txt == '', txt)
    # 手動修改拼音
    if t.is_hidden('#panel'): t.click('[data-a=panel]')
    inp = t.locator('[data-pyid]').first
    inp.fill('xiè xie'); inp.dispatch_event('change'); t.wait_for_timeout(200)
    check('手動改拼音', t.evaluate("window.__bb.D.words[0].py") == 'xiè xie')
    check('改拼音同步注音', re.search('[ㄅ-ㄩ]', t.evaluate("window.__bb.D.words[0].zy")) is not None)
    t.click('[data-a=panel]')
    # 泡泡移動與反彈
    t.evaluate("window.__bb.D.mt.base=100")
    t.wait_for_timeout(300)
    box = t.evaluate("(()=>{const f=document.querySelector('#field').getBoundingClientRect();return [...document.querySelectorAll('.bub')].map(b=>{const r=b.getBoundingClientRect();return r.left>=f.left-2&&r.right<=f.right+2&&r.top>=f.top-2&&r.bottom<=f.bottom+2})})()")
    check('泡泡留在畫面內（反彈）', all(box), box)
    # 速度
    t0 = t.evaluate('window.__bb.effT()'); t.wait_for_timeout(500); d1 = t.evaluate('window.__bb.effT()') - t0
    t.evaluate("(()=>{const s=document.querySelector('#speed');s.value=10;s.dispatchEvent(new Event('input',{bubbles:true}))})()")
    t0 = t.evaluate('window.__bb.effT()'); t.wait_for_timeout(500); d2 = t.evaluate('window.__bb.effT()') - t0
    check('速度可即時調整', d2 > d1 * 1.5, (d1, d2))
    # 暫停
    t.click('[data-a=freeze]'); a = t.evaluate('window.__bb.effT()'); t.wait_for_timeout(300)
    check('暫停移動', t.evaluate('window.__bb.effT()') == a); t.click('[data-a=freeze]')
    # 大小
    w0 = t.evaluate("document.querySelector('.bub').offsetWidth")
    t.evaluate("(()=>{const s=document.querySelector('#size');s.value=10;s.dispatchEvent(new Event('input',{bubbles:true}))})()"); t.wait_for_timeout(200)
    check('大小可調', t.evaluate("document.querySelector('.bub').offsetWidth") > w0)
    # 模式1 戳泡泡
    i = ids(t); n0 = t.evaluate('window.__sounds.pop')
    pop_by_id(t, i[0]); t.wait_for_timeout(300)
    check('戳破進正確清單', t.evaluate('window.__bb.D.rd.popped.length') == 1 and '謝謝' in t.inner_text('.lst.ok') or '谢谢' in t.inner_text('.lst.ok'))
    check('破掉有音效', t.evaluate('window.__sounds.pop') > n0)
    # 復原
    t.click('[data-a=undo]'); t.wait_for_timeout(200)
    check('復原', t.evaluate('window.__bb.D.rd.popped.length') == 0)
    # 快速加入
    t.fill('#quickIn', 'amigo'); t.press('#quickIn', 'Enter'); t.wait_for_timeout(400)
    check('輪中加入字詞', t.evaluate('window.__bb.D.rd.order.length') == 3 and t.locator('.bub').count() == 3)
    # 同時出現
    if t.is_hidden('#panel'): t.click('[data-a=panel]')
    t.select_option('#capSel', '3'); t.wait_for_timeout(100)
    t.click('[data-a=panel]')
    check('同時出現上限', t.locator('.bub').count() == 3)
    # 結束本輪 → 複習
    pop_by_id(t, i[0]); t.wait_for_timeout(200)
    t.click('[data-a=endround]'); t.wait_for_selector('.ov')
    check('結束本輪結算', t.evaluate("window.__bb.D.rd.st") == 'end' and t.evaluate('window.__bb.D.rd.rv.length') == 2)
    check('結算音效', t.evaluate('window.__sounds.end') >= 1)
    t.click('[data-a=review]'); t.wait_for_selector('.bub')
    check('只練複習清單', t.evaluate('window.__bb.D.rd.order.length') == 2)
    t.click('[data-a=endround]'); t.click('[data-a=again]'); t.wait_for_selector('.bub')
    check('全部重來', t.evaluate('window.__bb.D.rd.order.length') == 3 - 0 or t.evaluate('window.__bb.D.rd.order.length') >= 3)
    # 計時器
    if t.is_hidden('#panel'): t.click('[data-a=panel]')
    t.click('[data-a=tsel][data-v=d30]'); check('倒數 30 秒', '00:30' in t.inner_text('#tmr') or '00:29' in t.inner_text('#tmr'))
    t.click('[data-a=tsel][data-v=custom]'); t.fill('#custSec', '2'); t.dispatch_event('#custSec', 'change')
    check('自訂秒數', t.evaluate('window.__bb.D.tm.total') == 2)
    t.click('[data-a=panel]')
    t.click('[data-a=start]'); t.wait_for_timeout(2600)
    check('時間到自動結束本輪', t.evaluate('window.__bb.D.rd.st') == 'end' and t.evaluate('window.__bb.D.rd.why') == 'time')
    t.click('[data-a=closeov]')
    if t.is_hidden('#panel'): t.click('[data-a=panel]')
    t.click('[data-a=tsel][data-v=u]'); t.click('[data-a=tstart]'); t.wait_for_timeout(1200)
    check('碼表往上數', re.search('00:0[1-2]', t.inner_text('#tmTxt')) is not None, t.inner_text('#tmr'))
    t.click('[data-a=tpause]'); a = t.inner_text('#tmTxt'); t.wait_for_timeout(1100)
    check('碼表暫停', t.inner_text('#tmTxt') == a)
    t.click('[data-a=treset]'); check('碼表歸零', t.inner_text('#tmTxt') == '00:00')
    t.click('[data-a=tsel][data-v=off]'); t.click('[data-a=panel]')
    # 存清單
    if t.is_hidden('#panel'): t.click('[data-a=panel]')
    t.fill('#wordsIn', '一 二 三'); t.fill('#listName', '數字'); t.click('[data-a=listsave]')
    check('儲存清單', t.evaluate("window.__bb.S.lists.length") == 1)
    t.select_option('#listSel', ''); t.fill('#wordsIn', 'x'); t.select_option('#listSel', index=1)
    check('載入清單', t.input_value('#wordsIn') == '一 二 三')
    t.once('dialog', lambda d: d.accept()); t.click('[data-a=listdel]')
    check('刪除清單', t.evaluate("window.__bb.S.lists.length") == 0)
    # 靜音
    t.evaluate("document.querySelector('#muteChk').click()")
    check('靜音設定', t.evaluate('window.__bb.S.mute') is True)
    t.evaluate("document.querySelector('#muteChk').click()")
    # 刪字詞
    n = t.evaluate('window.__bb.D.words.length'); t.click('[data-a=delword]'); check('刪除單一字詞', t.evaluate('window.__bb.D.words.length') == n - 1)
    # ===== 進場方式、浮動設定面板 =====
    if t.is_visible('.ov'): t.click('[data-a=closeov]')
    if t.evaluate("window.__bb.D.rd.st") == 'run': t.click('[data-a=endround]'); t.click('[data-a=closeov]')
    apply_words(t, '一 二 三 四 五 六')
    t.select_option('#capSel', '0')
    y0 = t.evaluate("document.querySelector('#field').getBoundingClientRect().top")
    check('設定面板浮動不推擠泡泡區', t.is_visible('#panel') and t.evaluate("document.querySelector('#field').getBoundingClientRect().top") == y0 and t.evaluate("getComputedStyle(document.querySelector('#panel')).position") == 'absolute')
    t.click('[data-a=en][data-v=batch]')
    t.select_option('#enN', '1'); t.fill('#enGap', '2'); t.dispatch_event('#enGap', 'change')
    check('分批進來：選項出現', t.is_visible('#enOpts') and t.evaluate('window.__bb.D.set.en.m') == 'batch')
    t.click('[data-a=start]'); t.wait_for_timeout(400)
    check('分批：一開始只進 1 個', t.locator('.bub').count() == 1, t.locator('.bub').count())
    # 設定面板開著也能戳泡泡
    pop_by_id(t, t.evaluate("document.querySelector('.bub').dataset.id")); t.wait_for_timeout(300)
    check('開著設定也能戳泡泡', t.evaluate('window.__bb.D.rd.popped.length') == 1)
    t.wait_for_timeout(2200)
    check('分批：隔幾秒再進一個', t.locator('.bub').count() == 1, t.locator('.bub').count())
    t.wait_for_timeout(2200)
    check('分批：持續進來', t.locator('.bub').count() == 2, t.locator('.bub').count())
    # 上課中改成全部一次
    t.click('[data-a=en][data-v=all]'); t.wait_for_timeout(500)
    check('上課中改「全部一次」剩下的立刻進來', t.locator('.bub').count() == 5, t.locator('.bub').count())
    t.click('[data-a=endround]'); t.click('[data-a=closeov]')
    # 每次進 3 個
    t.click('[data-a=en][data-v=batch]'); t.select_option('#enN', '3'); t.fill('#enGap', '30'); t.dispatch_event('#enGap', 'change')
    t.click('[data-a=start]'); t.wait_for_timeout(400)
    check('分批：每次進 3 個', t.locator('.bub').count() == 3, t.locator('.bub').count())
    t.click('[data-a=endround]'); t.click('[data-a=closeov]')
    # 逐漸加快
    t.select_option('#enN', '1'); t.fill('#enGap', '10'); t.dispatch_event('#enGap', 'change')
    t.evaluate("document.querySelector('#enRamp').click()")
    check('逐漸加快：出現最短間隔欄位', t.is_visible('#enMin'))
    t.fill('#enMin', '3'); t.dispatch_event('#enMin', 'change')
    t.click('[data-a=start]'); t.wait_for_timeout(300)
    bs = t.evaluate("window.__bb.D.rd.order.map(id=>window.__bb.D.words.find(w=>w.id==id).m.born)")
    gaps = [round(bs[i+1]-bs[i], 3) for i in range(len(bs)-1)]
    check('逐漸加快：間隔越來越短、不低於最短', all(gaps[i] >= gaps[i+1] for i in range(len(gaps)-1)) and gaps[0] > gaps[-1] and min(gaps) >= 3*0.85 - 0.01, gaps)
    t.click('[data-a=endround]'); t.click('[data-a=closeov]')
    t.evaluate("document.querySelector('#enRamp').click()")
    t.click('[data-a=start]'); t.wait_for_timeout(300)
    bs = t.evaluate("window.__bb.D.rd.order.map(id=>window.__bb.D.words.find(w=>w.id==id).m.born)")
    gaps = [round(bs[i+1]-bs[i], 3) for i in range(len(bs)-1)]
    check('取消逐漸加快：間隔固定', len(set(gaps)) == 1, gaps)
    t.click('[data-a=endround]'); t.click('[data-a=closeov]')
    # 同時出現 1、2：排隊的從邊緣進來
    t.click('[data-a=en][data-v=all]'); t.select_option('#capSel', '1')
    t.click('[data-a=start]'); t.wait_for_timeout(400)
    check('同時出現 1 個', t.locator('.bub').count() == 1)
    pop_by_id(t, t.evaluate("document.querySelector('.bub').dataset.id")); t.wait_for_timeout(700)
    check('戳破後下一個才進來', t.locator('.bub').count() == 1 and t.evaluate('window.__bb.D.rd.popped.length') == 1)
    t.select_option('#capSel', '2'); t.wait_for_timeout(300)
    check('同時出現 2 個', t.locator('.bub').count() == 2)
    t.select_option('#capSel', '0'); t.click('[data-a=endround]'); t.click('[data-a=closeov]')
    # 配對 + 分批：目標一定是已經進來的字
    t.click('[data-a=mode][data-v=match]')
    apply_words(t, '你好=hola 謝謝=gracias 老師=profesor 學生=alumno')
    t.click('[data-a=en][data-v=batch]'); t.select_option('#enN', '1'); t.fill('#enGap', '30'); t.dispatch_event('#enGap', 'change')
    t.click('[data-a=start]'); t.wait_for_timeout(600)
    tg = t.evaluate('window.__bb.D.rd.target')
    check('配對分批：目標是已出現的泡泡', tg is not None and t.locator(f'.bub[data-id="{tg}"]').count() == 1, tg)
    t.click('[data-a=endround]'); t.click('[data-a=closeov]')
    t.click('[data-a=mode][data-v=say]'); t.click('[data-a=en][data-v=all]')
    # 連線卡住時不會一直停在首頁：逾時後顯示登入畫面
    hang = br.new_context(viewport={'width': 400, 'height': 800})
    held = []
    hang.route('**/gstatic.com/**', lambda r: held.append(r))
    hp = hang.new_page(); hp.goto(BASE + '?tmo=1500'); hp.click('[data-a=teacher]'); hp.wait_for_selector('#loginBtn', timeout=6000)
    check('Firebase 連線卡住：逾時後出現登入畫面與提示', '連線失敗' in hp.inner_text('#pwErr'), hp.inner_text('#pwErr'))
    hang.close()
    # ===== 雲端清單、去重複、回到泡泡區、團隊計分、輸出圖片 =====
    if t.evaluate("window.__bb.D.rd.st") == 'run': t.click('[data-a=endround]')
    if t.is_visible('.ov'): t.click('[data-a=closeov]')
    if t.is_hidden('#panel'): t.click('[data-a=panel]')
    t.fill('#wordsIn', '蘋果 香蕉 蘋果 西瓜\nmanzana, manzana'); t.click('[data-a=apply]'); t.wait_for_timeout(500)
    check('自動去掉重複字詞', t.evaluate('window.__bb.D.words.length') == 4, t.evaluate('window.__bb.D.words.length'))
    t.evaluate("document.querySelector('#dedupeChk').click()")
    t.fill('#wordsIn', '蘋果 蘋果'); t.click('[data-a=apply]'); t.wait_for_timeout(300)
    check('關閉去重複後可重複', t.evaluate('window.__bb.D.words.length') == 2)
    t.evaluate("document.querySelector('#dedupeChk').click()")
    t.fill('#wordsIn', '貓 狗 魚 鳥'); t.fill('#listName', '動物'); t.click('[data-a=listsave]'); t.wait_for_timeout(300)
    check('清單存到雲端', t.evaluate("JSON.parse(localStorage.getItem('bb_cloud_lists')).lists.some(l=>l.name=='動物')"))
    t.evaluate("(()=>{const s=JSON.parse(localStorage.getItem('bb_state_v1'));s.lists=[];s.cur='';localStorage.setItem('bb_state_v1',JSON.stringify(s))})()")
    t.reload(); teacher_login(t)
    check('換裝置（本機清單清空）從雲端取回清單', t.evaluate("window.__bb.S.lists.some(l=>l.name=='動物')"))
    t.click('[data-a=panel]'); t.select_option('#listSel', index=1); t.click('[data-a=apply]'); t.wait_for_timeout(500)
    # 團隊計分
    t.select_option('#teamN', '2'); t.wait_for_timeout(200)
    t.locator('[data-teamname="0"]').fill('紅'); t.locator('[data-teamname="0"]').dispatch_event('change')
    t.click('[data-a=panel]')
    check('隊伍計分板出現', t.locator('#teams .team').count() == 2 and '紅' in t.inner_text('#teams'))
    t.click('[data-a=start]'); t.wait_for_selector('.bub')
    i0 = ids(t)
    pop_by_id(t, i0[0]); t.wait_for_timeout(300); pop_by_id(t, i0[1]); t.wait_for_timeout(300); pop_by_id(t, i0[2]); t.wait_for_timeout(300)
    check('每戳破一個換下一隊（紅2、第2隊1）', t.evaluate('window.__bb.teamScores()') == [2, 1], t.evaluate('window.__bb.teamScores()'))
    t.click('#teams .team >> nth=1'); pop_by_id(t, i0[3]); t.wait_for_timeout(300)
    check('老師可手動選隊伍', t.evaluate('window.__bb.teamScores()') == [2, 2])
    # 戳破的字點一下放回泡泡區
    n_ok = t.locator('.lst.ok .wc.click').count()
    check('正確清單的字可點', n_ok == 4, n_ok)
    if t.is_visible('.ov'): t.click('[data-a=closeov]')
    t.locator('.lst.ok .wc.click').first.click(); t.wait_for_timeout(600)
    check('點正確清單的字放回泡泡區', t.evaluate('window.__bb.D.rd.popped.length') == 3 and t.locator('.bub').count() == 1 and t.evaluate('window.__bb.teamScores().reduce((a,b)=>a+b)') == 3)
    pop_by_id(t, t.evaluate("document.querySelector('.bub').dataset.id")); t.wait_for_timeout(700)
    # 結束後輸出圖片
    check('全部破完結算，贏家顯示', t.is_visible('.ov') and ('優勝' in t.inner_text('.ov') or '平手' in t.inner_text('.ov')), t.inner_text('.ov'))
    t.click('[data-a=again]'); t.wait_for_selector('.bub'); t.click('[data-a=endround]'); t.wait_for_selector('.ov')
    with t.expect_download() as dl: t.click('.ov [data-a=saveimg]')
    path = dl.value.path(); data = open(path, 'rb').read()
    check('老師輸出錯誤字詞圖片(PNG)', data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) > 5000, len(data))
    t.click('[data-a=closeov]')
    t.select_option('#teamN', '0') if False else None
    # 登出
    t.once('dialog', lambda d: d.accept()); t.click('[data-a=logout]'); t.wait_for_selector('[data-a=teacher]')
    check('登出回首頁並清除登入', t.evaluate("localStorage.getItem('bb_local_login')") is None)
    teacher_login(t)
    check('整體無 JS 錯誤(老師)', not errs, errs)

    # ===== 連線：老師 + 學生 =====
    t2 = ctx.new_page(); t2.on('pageerror', lambda e: errs.append(str(e)))
    t2.goto(BASE + '?local=1'); teacher_login(t2)
    apply_words(t2, '你好 謝謝 老師 學生')
    t2.wait_for_function("window.__bb.D.words.every(w=>w.py)", timeout=15000)
    t2.click('[data-a=openroom]'); t2.wait_for_selector('.code')
    code = t2.inner_text('.code'); check('開啟連線取得房號', re.fullmatch(r'\d{4}', code) is not None)
    s = ctx.new_page(); s.on('pageerror', lambda e: errs.append(str(e)))
    s.goto(BASE + '?local=1&room=9999'); s.wait_for_timeout(300)
    check('錯誤房號提示', '找不到' in s.inner_text('body'))
    s.goto(BASE + '?local=1&room=' + code); s.wait_for_selector('#field')
    check('學生進入', s.is_visible('.pill.live'))
    check('學生等老師', '等老師' in s.inner_text('#field'))
    # 模式1：學生不能戳
    t2.click('[data-a=start]'); s.wait_for_selector('.bub')
    check('學生看到泡泡', s.locator('.bub').count() == 4)
    pop_by_id(s, ids(s)[0]) if False else None
    s.evaluate("document.querySelector('.bub').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))"); s.wait_for_timeout(300)
    check('模式1 學生不能戳', s.evaluate('window.__bb.D.rd.popped.length') == 0)
    # 老師戳 → 學生同步
    pop_by_id(t2, ids(t2)[0]); s.wait_for_timeout(500)
    check('老師戳破學生同步', s.evaluate('window.__bb.D.rd.popped.length') == 1 and s.locator('.bub').count() == 3)
    # 同步速度、繁簡
    t2.evaluate("(()=>{const e=document.querySelector('#speed');e.value=9;e.dispatchEvent(new Event('input',{bubbles:true}))})()"); s.wait_for_timeout(400)
    check('速度同步', s.evaluate('window.__bb.D.mt.sp') == 9)
    t2.click('#bar [data-a=script][data-v=sc]'); s.wait_for_timeout(400)
    check('簡繁由老師控制', '学生' in s.inner_text('#field') or '谢谢' in s.inner_text('#field'))
    t2.click('#bar [data-a=script][data-v=tc]')
    # 模式2：學生戳
    t2.click('[data-a=mode][data-v=hear]'); t2.click('[data-a=start]'); s.wait_for_function("window.__bb.D.set.mode=='hear' && window.__bb.D.rd.st=='run' && window.__bb.D.rd.order.length==4"); s.wait_for_selector('.bub')
    s.evaluate("document.querySelector('.bub').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))"); s.wait_for_timeout(600)
    check('模式2 學生戳破老師同步', t2.evaluate('window.__bb.D.rd.popped.length') == 1)
    # 計時同步
    if t2.is_hidden('#panel'): t2.click('[data-a=panel]')
    t2.click('[data-a=tsel][data-v=d60]'); t2.click('[data-a=tstart]'); s.wait_for_timeout(500)
    check('計時同步', re.search('00:(59|60|58)|01:00', s.inner_text('#tmr')) is not None, s.inner_text('#tmr'))
    t2.click('[data-a=tsel][data-v=off]'); t2.click('[data-a=panel]')
    # 結束 → 學生看到結算
    t2.click('[data-a=endround]'); s.wait_for_selector('.ov')
    check('學生看到結算與複習清單', s.locator('.ov .wc').count() == 3)
    # 學生輸出圖片
    s.wait_for_selector('.ov')
    with s.expect_download() as dl2: s.click('.ov [data-a=saveimg]')
    d2 = open(dl2.value.path(), 'rb').read()
    check('學生也能輸出錯誤字詞圖片', d2[:8] == b'\x89PNG\r\n\x1a\n' and len(d2) > 5000)
    # 老師把戳破的字放回，學生同步
    t2.click('[data-a=closeov]'); t2.click('[data-a=start]'); s.wait_for_function("window.__bb.D.rd.st=='run' && window.__bb.D.rd.order.length==4"); s.wait_for_selector('.bub')
    if t2.is_visible('.ov'): t2.click('[data-a=closeov]')
    first = t2.evaluate('window.__bb.D.rd.order[0]'); pop_by_id(t2, first); s.wait_for_timeout(600)
    check('學生看到字被戳破', s.locator(f'.bub[data-id="{first}"]').count() == 0)
    t2.locator('.lst.ok .wc.click').first.click(); s.wait_for_timeout(700)
    check('放回泡泡區後學生也看得到', s.locator(f'.bub[data-id="{first}"]').count() == 1 and s.evaluate('window.__bb.D.rd.popped.length') == 0)
    # 配對
    t3 = ctx.new_page(); t3.goto(BASE + '?local=1'); teacher_login(t3)
    apply_words(t3, '你好=hola 謝謝=gracias 老師=profesor 學生')
    t3.click('[data-a=mode][data-v=match]'); t3.click('[data-a=openroom]'); t3.wait_for_selector('.code'); c3 = t3.inner_text('.code')
    s3 = ctx.new_page(); s3.goto(BASE + '?local=1&room=' + c3); s3.wait_for_selector('#field')
    t3.click('[data-a=start]'); s3.wait_for_selector('.bub')
    check('配對：未配對字詞排除', t3.evaluate('window.__bb.D.rd.order.length') == 3)
    check('配對：顯示目標詞', s3.locator('.target .big').count() == 1)
    check('配對：泡泡是西文', 'hola' in s3.inner_text('#field') or 'gracias' in s3.inner_text('#field'))
    tg = s3.evaluate('window.__bb.D.rd.target'); wrong = [x for x in ids(s3) if x != tg and x in s3.evaluate('window.__bb.D.rd.order')][0]
    s3.evaluate(f"document.querySelector('.bub[data-id=\"{wrong}\"]').dispatchEvent(new PointerEvent('pointerdown',{{bubbles:true}}))"); s3.wait_for_timeout(500)
    check('配對：點錯不破並記錯', s3.evaluate('window.__bb.D.rd.popped.length') == 0 and t3.evaluate('window.__bb.D.rd.miss.length') >= 1)
    s3.evaluate(f"document.querySelector('.bub[data-id=\"{tg}\"]').dispatchEvent(new PointerEvent('pointerdown',{{bubbles:true}}))"); s3.wait_for_timeout(1500)
    check('配對：點對破掉並換下一題', t3.evaluate('window.__bb.D.rd.popped.length') == 1 and t3.evaluate('window.__bb.D.rd.target') != tg)
    # 結束連線 → 學生被告知
    t3.once('dialog', lambda d: d.accept()); t3.click('[data-a=endroom]'); s3.wait_for_timeout(600)
    check('結束連線學生收到', '房間已結束' in s3.inner_text('body') or '找不到' in s3.inner_text('body'))
    # 學生靜音、離開
    if s.locator('[data-a=closeov]').count(): s.click('[data-a=closeov]')
    s.click('#bMute'); check('學生靜音', s.evaluate('window.__bb.S.mute') is True)
    s.click('[data-a=leave]'); check('學生離開回首頁', s.is_visible('[data-a=teacher]'))
    # 學生輸入房號加入
    s.fill('#joinIn', code); s.click('[data-a=join]'); s.wait_for_selector('#field'); check('輸入房號加入', s.is_visible('.pill.live'))
    s.evaluate("document.querySelector('#overlay').innerHTML=''"); s.click('[data-a=leave]'); s.fill('#joinIn', 'ab'); s.click('[data-a=join]'); check('房號格式錯誤', '找不到' in s.inner_text('#joinErr'))
    # 單機（不開連線）能玩
    check('整體無 JS 錯誤(全部)', not errs, errs)
    br.close()
bad = [n for n, ok in res if not ok]
print(f'\n{len(res)-len(bad)}/{len(res)} 通過'); sys.exit(1 if bad else 0)
