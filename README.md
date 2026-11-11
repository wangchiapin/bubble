# 泡泡字詞 · Burbujas de palabras

上課小工具：字詞變成泡泡在畫面裡飄，老師後台直接操作，學生用連結同步看。

- 老師：打開網頁 → 我是老師 → 密碼 → 設定輸入字詞 → 開啟連線 → 複製學生連結
- 學生：開連結（或輸入 4 位房號），不用登入
- 模式：1 學生唸、老師戳；2 老師唸、學生戳；配對（`你好=hola`）
- 計時：整輪倒數（預設或自訂秒數）、碼表；時間到自動結束並產生複習清單
- 後端：Firebase memorma-24dab，集合 `bubble_rooms`（規則在 game-kit 私有 repo）
- 測試：`python3 tests/test_bubbles.py`（Playwright，65 項）
