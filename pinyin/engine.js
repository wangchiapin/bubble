/* ===== 拼音引擎：繁/簡轉換 + 台灣讀音規則 + 輕聲還原 ===== */
const Engine = (function () {
  const { pinyin } = pinyinPro;
  const conv = OpenCC.Converter({ from: 't', to: 'cn' });
  const HAN = /\p{Script=Han}/u;
  const WORDCH = /[\p{L}\p{N}_]/u;

  /* ---------- 聲調工具 ---------- */
  const TONE_MARKS = {
    1: 'āēīōūǖ',
    2: 'áéíóúǘńḿ',
    3: 'ǎěǐǒǔǚň',
    4: 'àèìòùǜǹ'
  };
  function toneOf(s) {
    if (!s) return 0;
    for (const t of [1, 2, 3, 4]) {
      for (const c of TONE_MARKS[t]) if (s.includes(c)) return t;
    }
    return 5;
  }
  function stripTone(s) {
    return s.normalize('NFD').replace(/[\u0300\u0301\u0304\u030c]/g, '').normalize('NFC');
  }
  const VOWEL_TONES = { a: 'āáǎà', e: 'ēéěè', i: 'īíǐì', o: 'ōóǒò', u: 'ūúǔù', 'ü': 'ǖǘǚǜ' };
  // le4 → lè ；nv3 → nǚ ；已有聲調符號就原樣回傳
  function numToMark(s) {
    s = s.trim().replace(/v/g, 'ü').replace(/u:/g, 'ü');
    const m = s.match(/^([a-zü]+)([1-5])$/i);
    if (!m) return s;
    const base = m[1], t = +m[2];
    if (t === 5) return base;
    const low = base.toLowerCase();
    let idx = -1;
    if (low.includes('a')) idx = low.indexOf('a');
    else if (low.includes('e')) idx = low.indexOf('e');
    else if (low.includes('ou')) idx = low.indexOf('o');
    else for (let i = low.length - 1; i >= 0; i--) if ('aeiouü'.includes(low[i])) { idx = i; break; }
    if (idx < 0) return base;
    return base.slice(0, idx) + VOWEL_TONES[low[idx]][t - 1] + base.slice(idx + 1);
  }

  /* ---------- 內建台灣讀音規則 ---------- */
  // 格式：詞=拼音（音節用空格分開）。越長的詞越優先。
  const BUILTIN_RULES = `
# 常見台灣讀音（GoodTeacher 的語境規則另外內建，在下面處理）
垃圾=lè sè
期=qí
危=wéi
微=wéi
血=xiě
東西=dōng xī
便宜=pián yí
謝謝=xiè xie
`;

  /* ---------- GoodTeacher 語境規則（由 rules.csv 轉入） ---------- */
  const GT = (typeof GT_RULES !== 'undefined') ? GT_RULES : { rules: [], defaults: {} };
  const GT_BY_CHAR = new Map();
  for (const r of GT.rules) {
    if (!GT_BY_CHAR.has(r[0])) GT_BY_CHAR.set(r[0], []);
    GT_BY_CHAR.get(r[0]).push(r);
  }
  const GT_COUNT = GT.rules.length;
  const DIGIT = /^[0-9０-９]$/;
  const PUNCT = /^\p{P}$/u;

  // 這些字若被函式庫讀成輕聲，就保持輕聲（語助詞、詞尾）
  const KEEP_NEUTRAL = new Set(Array.from('的了著着嗎吗呢吧啊啦呀哇吶哦喔嘛咧麼么們们子個个得地過过一不'));
  // 簡化後會讀錯的繁體字，保留繁體讓函式庫直接查
  const KEEP_TRAD = new Set(['髮']);

  function parseRules(text) {
    const map = new Map();
    const errors = [];
    let maxLen = 1;
    const add = (k, v) => { if (k) { map.set(k, v); maxLen = Math.max(maxLen, Array.from(k).length); } };
    for (const raw of (text || '').split(/\r?\n/)) {
      const line = raw.replace(/#.*$/, '').trim();
      if (!line) continue;
      const i = line.search(/[=＝]/);
      if (i < 1) { errors.push(raw); continue; }
      const key = line.slice(0, i).trim();
      const syl = line.slice(i + 1).trim().split(/[\s,，、]+/).filter(Boolean).map(numToMark);
      if (syl.length !== Array.from(key).length) { errors.push(raw); continue; }
      add(key, syl);
      // 同時登錄簡體寫法
      try { const s = conv(key); if (s !== key && Array.from(s).length === Array.from(key).length) add(s, syl); } catch (e) {}
    }
    return { map, maxLen, errors };
  }

  function buildRules(customText) {
    const builtin = parseRules(BUILTIN_RULES);
    const custom = parseRules(customText);
    return { builtin, custom, errors: custom.errors, customCount: custom.map.size };
  }

  /* ---------- 函式庫呼叫 ---------- */
  function perChar(str, chars) {
    let res = [];
    try { res = pinyin(str, { type: 'all' }); } catch (e) { res = []; }
    if (res.length !== chars.length) {
      res = chars.map(c => { try { return pinyin(c, { type: 'all' })[0] || {}; } catch (e) { return {}; } });
    }
    return res.map(r => (r && r.isZh ? r.result : ''));
  }

  function candidates(ch, current) {
    const set = [];
    const push = s => { if (s && !set.includes(s)) set.push(s); };
    push(current);
    const forms = [ch];
    try { const s = conv(ch); if (s !== ch) forms.push(s); } catch (e) {}
    for (const f of forms) {
      try { for (const s of pinyin(f, { multiple: true, type: 'array' })) push(s); } catch (e) {}
    }
    for (const r of (GT_BY_CHAR.get(ch) || [])) push(r[1]);
    if (GT.defaults[ch]) push(GT.defaults[ch]);
    if (ch === '一') ['yī', 'yí', 'yì', 'yi'].forEach(push);
    if (ch === '不') ['bù', 'bú', 'bu'].forEach(push);
    if (current && toneOf(current) !== 5) push(stripTone(current));
    return set;
  }

  /* ---------- 單行分析 ---------- */
  function ctxKey(chars, i) {
    return (chars[i - 1] || '') + '|' + chars[i] + '|' + (chars[i + 1] || '');
  }

  function analyzeLine(line, rules, manual) {
    const chars = Array.from(line);
    if (!chars.length) return [];

    // 1) 繁→簡（一對一），讓函式庫用較完整的簡體字典判斷讀音
    let simp = chars.slice();
    try {
      const s = Array.from(conv(line));
      if (s.length === chars.length) simp = s;
    } catch (e) {}
    for (let i = 0; i < chars.length; i++) if (KEEP_TRAD.has(chars[i])) simp[i] = chars[i];

    const py = perChar(simp.join(''), chars);
    const trad = perChar(chars.join(''), chars);
    const locked = new Array(chars.length).fill(false);

    // 2) 輕聲還原：台灣習慣多數詞尾保持原調（語助詞與詞尾字除外）
    for (let i = 0; i < chars.length; i++) {
      if (!HAN.test(chars[i]) || !py[i]) continue;
      if (toneOf(py[i]) !== 5 || KEEP_NEUTRAL.has(chars[i])) continue;
      const base = stripTone(py[i]);
      if (trad[i] && toneOf(trad[i]) !== 5 && stripTone(trad[i]) === base) { py[i] = trad[i]; continue; }
      const alt = candidates(chars[i], '').find(c => toneOf(c) !== 5 && stripTone(c) === base);
      if (alt) py[i] = alt;
    }

    // 3) 詞對詞規則（最長詞優先）：先內建，再使用者自訂（自訂的會鎖定，不被後面改掉）
    applyWords(rules.builtin, false);
    applyWords(rules.custom, true);
    function applyWords(r, lock) {
      let i = 0;
      while (i < chars.length) {
        let hit = 0;
        for (let L = Math.min(r.maxLen, chars.length - i); L >= 1; L--) {
          const syl = r.map.get(chars.slice(i, i + L).join(''));
          if (syl) {
            for (let k = 0; k < L; k++) { py[i + k] = syl[k]; if (lock) locked[i + k] = true; }
            hit = L; break;
          }
        }
        i += hit || 1;
      }
    }

    // 4) GoodTeacher 語境規則：看前後字決定讀音，第一條符合的生效；都不符合就用預設讀音
    //    一／不 要看後一個字的聲調，所以最後才處理
    const baseTone = k => {
      const r = py[k];
      if (!r) return 0;
      const t = toneOf(r);
      if (t !== 5) return t;
      const d = GT.defaults[chars[k]] || (perChar(simp[k], [simp[k]])[0]);
      return toneOf(d);
    };
    const tokOk = (tok, k) => {
      if (k < 0 || k >= chars.length) return false;
      const c = chars[k];
      if (tok[0] === '@') {
        switch (tok) {
          case '@GT_HANZI': return HAN.test(c);
          case '@GT_DIG': return DIGIT.test(c);
          case '@GT_PUNCT': return PUNCT.test(c);
          case '@GT_T4YI': case '@GT_T4BU': return HAN.test(c) && baseTone(k) === 4;
          case '@GT_T123YI': { const t = HAN.test(c) ? baseTone(k) : 0; return t >= 1 && t <= 3; }
          default: return false;
        }
      }
      return tok.includes(c);
    };
    const ruleOk = (r, k) => {
      const prev = r[2], next = r[3];
      for (let j = 0; j < prev.length; j++) if (!tokOk(prev[prev.length - 1 - j], k - 1 - j)) return false;
      for (let j = 0; j < next.length; j++) if (!tokOk(next[j], k + 1 + j)) return false;
      return true;
    };
    const gtPass = onlyYiBu => {
      for (let k = 0; k < chars.length; k++) {
        const c = chars[k];
        if (locked[k] || ((c === '一' || c === '不') !== onlyYiBu)) continue;
        const list = GT_BY_CHAR.get(c);
        if (!list) continue;
        const hit = list.find(r => ruleOk(r, k));
        py[k] = hit ? hit[1] : (GT.defaults[c] || py[k]);
      }
    };
    gtPass(false);
    gtPass(true);

    // 5) 使用者在畫面上點選過的讀音
    for (let k = 0; k < chars.length; k++) {
      const m = manual && manual[ctxKey(chars, k)];
      if (m && HAN.test(chars[k])) py[k] = m;
    }

    // 6) 組成顯示單位
    const units = [];
    let k = 0;
    while (k < chars.length) {
      const c = chars[k];
      if (HAN.test(c)) {
        units.push({ kind: 'han', text: c, py: py[k] || '', ctx: ctxKey(chars, k) });
        k++;
      } else if (/\s/.test(c)) {
        units.push({ kind: 'space', text: ' ' });
        k++;
      } else if (WORDCH.test(c)) {
        let w = c; k++;
        while (k < chars.length && !HAN.test(chars[k]) &&
          (WORDCH.test(chars[k]) || (/['’\-]/.test(chars[k]) && k + 1 < chars.length && WORDCH.test(chars[k + 1])))) { w += chars[k]; k++; }
        units.push({ kind: 'latin', text: w });
      } else {
        units.push({ kind: 'punct', text: c });
        k++;
      }
    }
    return units;
  }

  function analyze(text, customText, manual) {
    const rules = buildRules(customText);
    const lines = (text || '').replace(/\r/g, '').split('\n').map(l => analyzeLine(l, rules, manual));
    return { lines, rules };
  }

  /* ---------- 拼音 → 注音 ---------- */
  const ZY_INIT = { b: 'ㄅ', p: 'ㄆ', m: 'ㄇ', f: 'ㄈ', d: 'ㄉ', t: 'ㄊ', n: 'ㄋ', l: 'ㄌ', g: 'ㄍ', k: 'ㄎ', h: 'ㄏ',
    j: 'ㄐ', q: 'ㄑ', x: 'ㄒ', zh: 'ㄓ', ch: 'ㄔ', sh: 'ㄕ', r: 'ㄖ', z: 'ㄗ', c: 'ㄘ', s: 'ㄙ' };
  const ZY_FINAL = {
    a: 'ㄚ', o: 'ㄛ', e: 'ㄜ', 'ê': 'ㄝ', ai: 'ㄞ', ei: 'ㄟ', ao: 'ㄠ', ou: 'ㄡ', an: 'ㄢ', en: 'ㄣ', ang: 'ㄤ', eng: 'ㄥ', er: 'ㄦ', ong: 'ㄨㄥ',
    i: 'ㄧ', ia: 'ㄧㄚ', io: 'ㄧㄛ', ie: 'ㄧㄝ', iai: 'ㄧㄞ', iao: 'ㄧㄠ', iu: 'ㄧㄡ', iou: 'ㄧㄡ', ian: 'ㄧㄢ', in: 'ㄧㄣ', iang: 'ㄧㄤ', ing: 'ㄧㄥ', iong: 'ㄩㄥ',
    u: 'ㄨ', ua: 'ㄨㄚ', uo: 'ㄨㄛ', uai: 'ㄨㄞ', ui: 'ㄨㄟ', uei: 'ㄨㄟ', uan: 'ㄨㄢ', un: 'ㄨㄣ', uen: 'ㄨㄣ', uang: 'ㄨㄤ', ueng: 'ㄨㄥ',
    'ü': 'ㄩ', 'üe': 'ㄩㄝ', 'üan': 'ㄩㄢ', 'ün': 'ㄩㄣ'
  };
  const ZY_YW = {
    yi: 'ㄧ', ya: 'ㄧㄚ', yo: 'ㄧㄛ', ye: 'ㄧㄝ', yai: 'ㄧㄞ', yao: 'ㄧㄠ', you: 'ㄧㄡ', yan: 'ㄧㄢ', yin: 'ㄧㄣ', yang: 'ㄧㄤ', ying: 'ㄧㄥ', yong: 'ㄩㄥ',
    yu: 'ㄩ', yue: 'ㄩㄝ', yuan: 'ㄩㄢ', yun: 'ㄩㄣ',
    n: 'ㄣ', ng: 'ㄣ', m: 'ㄇ', hm: 'ㄏㄇ', hng: 'ㄏㄥ',   // 嗯、呣、哼等嘆詞
    wu: 'ㄨ', wa: 'ㄨㄚ', wo: 'ㄨㄛ', wai: 'ㄨㄞ', wei: 'ㄨㄟ', wan: 'ㄨㄢ', wen: 'ㄨㄣ', wang: 'ㄨㄤ', weng: 'ㄨㄥ'
  };
  const ZY_TONE = { 1: '', 2: 'ˊ', 3: 'ˇ', 4: 'ˋ', 5: '˙' };
  // 回傳 { syms: ['ㄋ','ㄧ'], tone: 3, text: 'ㄋㄧˇ' }；看不懂的拼音回傳 null
  function toZhuyin(py) {
    if (!py) return null;
    const tone = toneOf(py) || 5;
    let b = stripTone(py).toLowerCase().replace(/v/g, 'ü').replace(/u:/g, 'ü');
    let sym = null;
    if (ZY_YW[b]) sym = ZY_YW[b];
    else if (/^(zh|ch|sh|r|z|c|s)i$/.test(b)) sym = ZY_INIT[b.slice(0, -1)];
    else if (b === 'ê' || ZY_FINAL[b] && /^(a|o|e|ai|ei|ao|ou|an|en|ang|eng|er)$/.test(b)) sym = ZY_FINAL[b];
    else {
      const m = b.match(/^(zh|ch|sh|[bpmfdtnlgkhjqxrzcs])(.+)$/);
      if (m) {
        let fin = m[2];
        if (/^[jqx]$/.test(m[1]) && fin[0] === 'u') fin = 'ü' + fin.slice(1);   // ju → jü
        if (ZY_FINAL[fin]) sym = ZY_INIT[m[1]] + ZY_FINAL[fin];
      }
    }
    if (!sym) return null;
    const syms = Array.from(sym);
    const text = tone === 5 ? '˙' + sym : sym + ZY_TONE[tone];
    return { syms, tone, text };
  }

  /* ---------- 文字輸出 ---------- */
  const PUNC = { '，': ',', '。': '.', '？': '?', '！': '!', '：': ':', '；': ';', '、': ',', '「': '“', '」': '”', '『': '‘', '』': '’', '（': '(', '）': ')', '～': '~', '…': '...', '⋯': '...' };
  const OPENERS = new Set(['“', '‘', '(', '《', '〈', '¿', '¡', '«', '[']);
  const ENDERS = /[。！？!?；;…]/;

  function pinyinLine(seg, script) {
    let out = '', pendingOpen = '';
    for (const u of seg) {
      if (u.kind === 'space') continue;
      let piece = '';
      let attach = false;
      if (u.kind === 'han') { const z = script === 'zhuyin' ? toZhuyin(u.py) : null; piece = z ? z.text : (u.py || u.text); }
      else if (u.kind === 'latin') piece = u.text;
      else {
        const p = PUNC[u.text] !== undefined ? PUNC[u.text] : u.text;
        if (OPENERS.has(p)) { pendingOpen += p; continue; }
        piece = p;
        attach = /\p{P}/u.test(p);   // 表情符號等不是標點，要和前後字分開
        if (!attach) { out += (out ? ' ' : '') + pendingOpen + piece; pendingOpen = ''; continue; }
      }
      if (attach) out += piece;
      else out += (out ? ' ' : '') + pendingOpen + piece, pendingOpen = '';
    }
    return (out + pendingOpen).trim();
  }

  function textOutput(lines, mode, script) {
    const out = [];
    for (const units of lines) {
      if (!units.length || units.every(u => u.kind === 'space')) { out.push(''); continue; }
      const segs = [];
      let cur = [];
      for (const u of units) {
        cur.push(u);
        if (u.kind === 'punct' && ENDERS.test(u.text)) { segs.push(cur); cur = []; }
      }
      if (cur.length) segs.push(cur);
      for (const seg of segs) {
        const han = seg.map(u => u.text).join('').trim();
        if (!han) continue;
        if (!seg.some(u => u.kind === 'han')) { out.push(han); continue; }   // 沒有漢字就不用加拼音
        let py = pinyinLine(seg, script);
        // 整句（以句號、問號、驚嘆號結尾）才把句首字母大寫
        if (/[.?!…]$/.test(py) || /[”’)]$/.test(py) && /[.?!]/.test(py.slice(-3))) {
          py = py.replace(/\p{L}/u, ch => ch.toUpperCase());
        }
        if (mode === 'bracket') out.push(han + ' (' + py + ')');
        else { out.push(han); out.push(py); }
      }
    }
    return out.join('\n').replace(/\n{3,}/g, '\n\n').trim();
  }

  return { analyze, candidates, textOutput, toZhuyin, numToMark, toneOf, stripTone, BUILTIN_RULES, GT_COUNT, parseRules, buildRules, ctxKey };
})();
