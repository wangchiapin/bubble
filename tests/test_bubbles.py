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
    p.click('[data-a=teacher]')
    if not p.locator('#pwIn').count():
        p.wait_for_selector('#field'); return
    p.fill('#pwIn', 'wrong'); p.click('[data-a=login]')
    check('密碼錯誤顯示提示', p.inner_text('#pwErr') != '')
    p.fill('#pwIn', 'bubble2026'); p.click('[data-a=login]')
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
    teacher_login(t)
    check('進入老師後台', t.is_visible('#ctl'))
    # 解析
    r = t.evaluate("window.__bb.parseWords('你好 謝謝 老師\\npor favor, hola, gracias\\n你好=hola')")
    check('解析：中文空白、西文逗號、配對', len(r) == 7 and r[6]['tr'] == ['hola'] and r[3]['k'] == 'lat', r)
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
    s.click('[data-a=closeov]'); s.click('#bMute'); check('學生靜音', s.evaluate('window.__bb.S.mute') is True)
    s.click('[data-a=leave]'); check('學生離開回首頁', s.is_visible('[data-a=teacher]'))
    # 學生輸入房號加入
    s.fill('#joinIn', code); s.click('[data-a=join]'); s.wait_for_selector('#field'); check('輸入房號加入', s.is_visible('.pill.live'))
    s.evaluate("document.querySelector('#overlay').innerHTML=''"); s.click('[data-a=leave]'); s.fill('#joinIn', 'ab'); s.click('[data-a=join]'); check('房號格式錯誤', '找不到' in s.inner_text('#joinErr'))
    # 單機（不開連線）能玩
    check('整體無 JS 錯誤(全部)', not errs, errs)
    br.close()
bad = [n for n, ok in res if not ok]
print(f'\n{len(res)-len(bad)}/{len(res)} 通過'); sys.exit(1 if bad else 0)
