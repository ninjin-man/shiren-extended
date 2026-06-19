// =====================================================================
// js/config/constants.js
// 画面サイズ・タイルサイズ・ゲーム状態などの定数群と、
// アイテム／モンスターのデータテーブル、汎用ユーティリティ関数を集約する。
// 他のどのモジュールよりも先に読み込まれることを前提とし、
// このファイルは他のゲームモジュールに依存しない（依存して良いのは標準APIのみ）。
// =====================================================================

// --- 画面・タイル関連 ---
export const TILE_SIZE = 32;        // 1タイルのピクセルサイズ
export const VIEW_COLS = 11;        // カメラに映るタイル数（横）
export const VIEW_ROWS = 9;         // カメラに映るタイル数（縦）
export const HUD_HEIGHT = 46;       // Canvas最上部、ステータス＋ログ描画用の高さ(px)

// --- ダンジョン全体のサイズ（カメラより十分大きくし、スクロールを発生させる） ---
export const MAP_WIDTH = 34;
export const MAP_HEIGHT = 22;

// --- 持ち物の最大数 ---
export const MAX_INV = 8;

// --- ゲームステート（タイムライン・マネージャーが参照する状態機械） ---
export const GameState = Object.freeze({
    INPUT_WAIT: 'INPUT_WAIT', // プレイヤーの入力待ち
    ANIMATION: 'ANIMATION',   // 移動・攻撃アニメーション中（入力不可）
    MENU: 'MENU',             // Canvas内ポップアップメニュー操作中
    AIM: 'AIM',                // アイテムを投げる方向選択中
    GAMEOVER: 'GAMEOVER',      // ゲームオーバー（リトライ待ち）
});

// --- 地形タイルの値 ---
export const TILE_WALL = 1;
export const TILE_FLOOR = 0;
export const TILE_STAIRS = 2;

// =====================================================================
// --- 汎用ユーティリティ ---
// =====================================================================
export function randInt(min, max) {
    return min + Math.floor(Math.random() * (max - min + 1));
}

export function shuffleArray(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
}

export function tileKey(x, y) {
    return `${x},${y}`;
}

// =====================================================================
// --- RPGデータテーブル：武器・防具・草・巻物・食料・モンスター・罠 ---
// =====================================================================
export const weaponTypes = [
    { name: '木の剣', atk: 3 },
    { name: '銅の剣', atk: 5 },
    { name: '氷の剣', atk: 6 },
    { name: '鉄甲の剣', atk: 8 },
];

export const shieldTypes = [
    { name: '皮の盾', def: 2 },
    { name: '鉄の盾', def: 4 },
    { name: '竜の盾', def: 6 },
];

// 草・巻物は「種類単位」で識別フラグを持つ（同じ種類なら一度識別すれば全部わかる）
export const herbTypes = [
    { name: '薬草', effect: 'heal', identified: false, disguise: null },
    { name: '毒草', effect: 'poison', identified: false, disguise: null },
    { name: '目つぶし草', effect: 'blind', identified: false, disguise: null },
    { name: '怪力の種', effect: 'strength', identified: false, disguise: null },
    { name: '全回復草', effect: 'fullheal', identified: false, disguise: null },
];

export const scrollTypes = [
    { name: '識別の巻物', effect: 'identify', identified: false, disguise: null },
    { name: '強化の巻物', effect: 'enchant', identified: false, disguise: null },
    { name: 'テレポートの巻物', effect: 'teleport', identified: false, disguise: null },
    { name: '弱化の巻物', effect: 'weaken', identified: false, disguise: null },
];

export const foodTypes = [
    { name: 'おにぎり', satiety: 50 },
];

export const monsterTypes = [
    { name: 'マムル', color: '#ff4444', hp: 12, atk: 4, def: 1, exp: 3 },
    { name: 'チンタラ', color: '#ffaa00', hp: 8, atk: 3, def: 0, exp: 2 },
    { name: 'オオイカリグモ', color: '#aa44ff', hp: 14, atk: 5, def: 2, exp: 5 },
];

export const trapTypeList = ['damage', 'poison_gas', 'paralyze', 'hunger_drain', 'warp'];

// =====================================================================
// --- アイテムの未識別（変装）名管理 ---
// =====================================================================
export function assignDisguises() {
    const herbAdj = shuffleArray(['くさった', 'ねばねばの', 'きらきらの', 'あやしい', 'ひかる', 'とげとげの', 'しおれた', 'まっ黒な']);
    herbTypes.forEach((t, i) => { t.disguise = herbAdj[i % herbAdj.length] + '草'; });
    const scrollAdj = shuffleArray(['古ぼけた', 'にじんだ', '変な模様の', '焼け焦げた', '虫食いの', '輝く']);
    scrollTypes.forEach((t, i) => { t.disguise = scrollAdj[i % scrollAdj.length] + '巻物'; });
}

export function resetIdentification() {
    herbTypes.forEach(t => { t.identified = false; });
    scrollTypes.forEach(t => { t.identified = false; });
}

// =====================================================================
// --- アイテムインスタンス生成・表示・識別 ---
// =====================================================================
let itemIdCounter = 1;

export function createRandomItem() {
    const roll = Math.random();
    if (roll < 0.20) {
        return { id: itemIdCounter++, category: 'weapon', typeIndex: randInt(0, weaponTypes.length - 1), enchant: randInt(-1, 2), identified: false };
    } else if (roll < 0.35) {
        return { id: itemIdCounter++, category: 'shield', typeIndex: randInt(0, shieldTypes.length - 1), enchant: randInt(-1, 2), identified: false };
    } else if (roll < 0.70) {
        return { id: itemIdCounter++, category: 'herb', typeIndex: randInt(0, herbTypes.length - 1) };
    } else if (roll < 0.90) {
        return { id: itemIdCounter++, category: 'scroll', typeIndex: randInt(0, scrollTypes.length - 1) };
    } else {
        return { id: itemIdCounter++, category: 'food', typeIndex: 0 };
    }
}

export function getItemDisplayName(item) {
    if (item.category === 'weapon') {
        const t = weaponTypes[item.typeIndex];
        return item.identified ? `${item.enchant >= 0 ? '+' : ''}${item.enchant} ${t.name}` : `${t.name}(未鑑定)`;
    }
    if (item.category === 'shield') {
        const t = shieldTypes[item.typeIndex];
        return item.identified ? `${item.enchant >= 0 ? '+' : ''}${item.enchant} ${t.name}` : `${t.name}(未鑑定)`;
    }
    if (item.category === 'herb') {
        const t = herbTypes[item.typeIndex];
        return t.identified ? t.name : t.disguise;
    }
    if (item.category === 'scroll') {
        const t = scrollTypes[item.typeIndex];
        return t.identified ? t.name : t.disguise;
    }
    if (item.category === 'food') {
        return foodTypes[item.typeIndex].name;
    }
    return '？？？';
}

export function isItemFullyIdentified(item) {
    if (item.category === 'weapon' || item.category === 'shield') return item.identified;
    if (item.category === 'herb') return herbTypes[item.typeIndex].identified;
    if (item.category === 'scroll') return scrollTypes[item.typeIndex].identified;
    return true;
}

export function identifyItem(item) {
    if (item.category === 'weapon' || item.category === 'shield') item.identified = true;
    else if (item.category === 'herb') herbTypes[item.typeIndex].identified = true;
    else if (item.category === 'scroll') scrollTypes[item.typeIndex].identified = true;
}

// 床アイコン色分け（renderer.js が使用）
export const ITEM_ICON_COLOR = {
    weapon: '#cccccc',
    shield: '#5599ff',
    herb: '#55cc55',
    scroll: '#ffffff',
    food: '#ff9944',
};
