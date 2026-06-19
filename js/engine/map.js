// =====================================================================
// js/engine/map.js
// ダンジョンの自動生成（部屋＋通路）、敵／アイテム／罠の配置、
// 視界（Fog of War）の判定、カメラ（プレイヤー追従スクロール）の計算を担当する。
// =====================================================================

import {
    MAP_WIDTH,
    MAP_HEIGHT,
    VIEW_COLS,
    VIEW_ROWS,
    TILE_WALL,
    TILE_FLOOR,
    TILE_STAIRS,
    randInt,
    tileKey,
    monsterTypes,
    trapTypeList,
    createRandomItem,
} from '../config/constants.js';
import { createMonster } from '../entities/monster.js';

// =====================================================================
// --- ダンジョン自動生成（区画割り部屋＋通路接続） ---
// =====================================================================
export function generateDungeon() {
    const grid = Array.from({ length: MAP_HEIGHT }, () => Array(MAP_WIDTH).fill(TILE_WALL));
    const rooms = [];
    const roomTarget = randInt(6, 9);
    let attempts = 0;

    while (rooms.length < roomTarget && attempts < 400) {
        attempts++;
        const rw = randInt(3, 6);
        const rh = randInt(3, 5);
        const rx = randInt(1, MAP_WIDTH - rw - 2);
        const ry = randInt(1, MAP_HEIGHT - rh - 2);
        const overlap = rooms.some(r =>
            rx - 1 < r.x + r.w + 1 && rx + rw + 1 > r.x - 1 &&
            ry - 1 < r.y + r.h + 1 && ry + rh + 1 > r.y - 1
        );
        if (overlap) continue;
        rooms.push({ x: rx, y: ry, w: rw, h: rh });
        for (let y = ry; y < ry + rh; y++) {
            for (let x = rx; x < rx + rw; x++) grid[y][x] = TILE_FLOOR;
        }
    }

    // 生成に失敗した場合の保険（最低限プレイ可能にする）
    if (rooms.length < 2) {
        rooms.length = 0;
        const r1 = { x: 1, y: 1, w: 5, h: 4 };
        const r2 = { x: MAP_WIDTH - 6, y: MAP_HEIGHT - 5, w: 5, h: 4 };
        [r1, r2].forEach(r => {
            for (let y = r.y; y < r.y + r.h; y++) {
                for (let x = r.x; x < r.x + r.w; x++) grid[y][x] = TILE_FLOOR;
            }
            rooms.push(r);
        });
    }

    // 部屋同士を通路（L字）で接続
    for (let i = 1; i < rooms.length; i++) {
        const a = rooms[i - 1], b = rooms[i];
        const ax = Math.floor(a.x + a.w / 2), ay = Math.floor(a.y + a.h / 2);
        const bx = Math.floor(b.x + b.w / 2), by = Math.floor(b.y + b.h / 2);
        let x = ax;
        while (x !== bx) { grid[ay][x] = TILE_FLOOR; x += (bx > ax ? 1 : -1); }
        grid[ay][bx] = TILE_FLOOR;
        let y = ay;
        while (y !== by) { grid[y][bx] = TILE_FLOOR; y += (by > ay ? 1 : -1); }
        grid[by][bx] = TILE_FLOOR;
    }

    return { grid, rooms };
}

// =====================================================================
// --- タイル判定 ---
// =====================================================================
export function isTileFree(x, y, grid, player, monsters, floorItems, floorTraps) {
    if (x < 0 || y < 0 || x >= MAP_WIDTH || y >= MAP_HEIGHT) return false;
    if (grid[y][x] !== TILE_FLOOR) return false;
    if (player && player.x === x && player.y === y) return false;
    if (monsters.some(m => m.isAlive && m.isAlive() && m.x === x && m.y === y)) return false;
    if (floorItems.some(fi => fi.x === x && fi.y === y)) return false;
    if (floorTraps.some(ft => ft.x === x && ft.y === y)) return false;
    return true;
}

export function randomFreeTile(grid, player, monsters, floorItems, floorTraps) {
    for (let i = 0; i < 400; i++) {
        const x = randInt(1, MAP_WIDTH - 2);
        const y = randInt(1, MAP_HEIGHT - 2);
        if (isTileFree(x, y, grid, player, monsters, floorItems, floorTraps)) return { x, y };
    }
    return null;
}

// =====================================================================
// --- フロアへの敵／アイテム／罠の配置 ---
// （プレイヤーは呼び出し側で既に開始位置へ置かれていること前提）
// =====================================================================
export function populateFloor(floorNum, grid, player) {
    const monsters = [];
    const floorItems = [];
    const floorTraps = [];

    const monsterCount = Math.min(2 + Math.floor(floorNum / 2), 7);
    for (let i = 0; i < monsterCount; i++) {
        const pos = randomFreeTile(grid, player, monsters, floorItems, floorTraps);
        if (!pos) continue;
        monsters.push(createMonster(randInt(0, monsterTypes.length - 1), pos.x, pos.y, floorNum));
    }

    const itemCount = randInt(3, 5);
    for (let i = 0; i < itemCount; i++) {
        const pos = randomFreeTile(grid, player, monsters, floorItems, floorTraps);
        if (!pos) continue;
        floorItems.push({ x: pos.x, y: pos.y, item: createRandomItem() });
    }

    const trapCount = 1 + Math.floor(floorNum / 3);
    for (let i = 0; i < trapCount; i++) {
        const pos = randomFreeTile(grid, player, monsters, floorItems, floorTraps);
        if (!pos) continue;
        floorTraps.push({ x: pos.x, y: pos.y, type: trapTypeList[randInt(0, trapTypeList.length - 1)], revealed: false });
    }

    return { monsters, floorItems, floorTraps };
}

// =====================================================================
// --- 罠の発動 ---
// ctx = { player, grid, monsters, floorItems, floorTraps }
// =====================================================================
export function triggerTrap(trap, ctx, addLog) {
    trap.revealed = true;
    const { player, grid, monsters, floorItems, floorTraps } = ctx;
    switch (trap.type) {
        case 'damage': {
            const d = randInt(5, 10);
            player.takeDamage(d);
            addLog(`トラップだ！矢が飛んできて${d}のダメージを受けた！`);
            break;
        }
        case 'poison_gas':
            player.statusEffects.poison = Math.max(player.statusEffects.poison, 6);
            addLog('毒の沼にはまった！からだが痛む…');
            break;
        case 'paralyze':
            player.statusEffects.paralyzed = Math.max(player.statusEffects.paralyzed, 2);
            addLog('しびれ茸の罠だ！体が動かない…');
            break;
        case 'hunger_drain':
            player.satiety = Math.max(0, player.satiety - 20);
            addLog('お腹のあたりが急に減った気がする…');
            break;
        case 'warp': {
            const pos = randomFreeTile(grid, player, monsters, floorItems, floorTraps);
            if (pos) {
                player.warpTo(pos.x, pos.y);
                addLog('ワープの罠だ！見知らぬ場所に飛ばされた。');
            }
            break;
        }
    }
}

// =====================================================================
// --- 視界（Fog of War）制御 ---
// 通路：プレイヤー隣接8方向＋自分のマスのみ可視。
// 部屋：プレイヤーがその部屋の矩形内に入った瞬間、部屋全体（壁の輪郭含む）が可視。
// 戻り値は "x,y" 文字列をキーとした Set。
// =====================================================================
export function computeVisibleTiles(player, rooms) {
    const visible = new Set();
    const containingRoom = rooms.find(r =>
        player.x >= r.x && player.x < r.x + r.w &&
        player.y >= r.y && player.y < r.y + r.h
    );

    if (containingRoom) {
        const x0 = Math.max(0, containingRoom.x - 1);
        const x1 = Math.min(MAP_WIDTH - 1, containingRoom.x + containingRoom.w);
        const y0 = Math.max(0, containingRoom.y - 1);
        const y1 = Math.min(MAP_HEIGHT - 1, containingRoom.y + containingRoom.h);
        for (let y = y0; y <= y1; y++) {
            for (let x = x0; x <= x1; x++) visible.add(tileKey(x, y));
        }
    } else {
        for (let dy = -1; dy <= 1; dy++) {
            for (let dx = -1; dx <= 1; dx++) {
                const x = player.x + dx, y = player.y + dy;
                if (x >= 0 && y >= 0 && x < MAP_WIDTH && y < MAP_HEIGHT) visible.add(tileKey(x, y));
            }
        }
    }
    return visible;
}

// =====================================================================
// --- カメラ（プレイヤー追従スクロール）の計算 ---
// 戻り値はビューポート左上のタイル座標 {camX, camY}
// =====================================================================
export function computeCamera(player) {
    const halfCols = Math.floor(VIEW_COLS / 2);
    const halfRows = Math.floor(VIEW_ROWS / 2);
    let camX = player.x - halfCols;
    let camY = player.y - halfRows;
    camX = Math.max(0, Math.min(camX, MAP_WIDTH - VIEW_COLS));
    camY = Math.max(0, Math.min(camY, MAP_HEIGHT - VIEW_ROWS));
    return { camX, camY };
}
