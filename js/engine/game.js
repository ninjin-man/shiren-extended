// =====================================================================
// js/engine/game.js
// 「タイムライン・マネージャー」。ゲーム全体の状態(state)を保持し、
// 厳密な同期ターン制（プレイヤー行動 → アニメーション待ち → 罠/階段判定 →
// 敵AI → 満腹度/状態異常処理 → 次ターン入力待ち）を制御する。
// また、Canvas内に直接描画されるポップアップメニュー（持ち物・あしもと・
// アイテムごとの行動選択・ゲームオーバー画面）の状態遷移もここで管理する。
// =====================================================================

import {
    GameState,
    MAP_WIDTH,
    MAP_HEIGHT,
    TILE_WALL,
    TILE_STAIRS,
    randInt,
    weaponTypes,
    shieldTypes,
    herbTypes,
    getItemDisplayName,
    resetIdentification,
    assignDisguises,
    tileKey,
} from '../config/constants.js';
import { generateDungeon, populateFloor, triggerTrap, randomFreeTile } from './map.js';
import { Player } from '../entities/player.js';
import { processMonsterAI } from '../entities/monster.js';

// =====================================================================
// --- グローバルなゲーム状態（renderer.js / input.js から読み取り専用で参照される） ---
// =====================================================================
export const state = {
    gameState: GameState.INPUT_WAIT,
    isTurnModeOnly: false,

    player: new Player(),

    grid: [],
    rooms: [],
    stairsPos: { x: 0, y: 0 },
    monsters: [],
    floorItems: [],
    floorTraps: [],
    floorNumber: 1,

    logLines: [],          // Canvas内ログ（最大2行）
    trailSet: new Set(),   // ミニマップ用：プレイヤーが歩いたマスの軌跡("x,y")の重複検査用
    trailOrder: [],        // ミニマップ用：軌跡を初訪問順に並べた配列({x,y})。線描画に使用。
    showMinimap: false,

    menuStack: [],          // Canvasポップアップメニューのスタック
    pendingThrowIdx: null,  // 投げるアイテムの持ち物index（AIM中）
    pendingFloorChange: false,
    lastFootNoticeId: null, // 直前にログ通知した足元アイテムのid（連投防止）

    gameOverInfo: null,     // { floor, level }
};

function addLog(text) {
    state.logLines.push(text);
    if (state.logLines.length > 2) state.logLines.shift();
}

// =====================================================================
// --- フロア生成・初期化 ---
// =====================================================================
export function initFloor(floorNum) {
    const { grid, rooms } = generateDungeon();
    state.grid = grid;
    state.rooms = rooms;
    state.floorNumber = floorNum;

    const startRoom = rooms[0];
    const startX = Math.floor(startRoom.x + startRoom.w / 2);
    const startY = Math.floor(startRoom.y + startRoom.h / 2);
    state.player.warpTo(startX, startY);

    const stairRoom = rooms[rooms.length - 1];
    state.stairsPos = { x: Math.floor(stairRoom.x + stairRoom.w / 2), y: Math.floor(stairRoom.y + stairRoom.h / 2) };
    state.grid[state.stairsPos.y][state.stairsPos.x] = TILE_STAIRS;

    const populated = populateFloor(floorNum, state.grid, state.player);
    state.monsters = populated.monsters;
    state.floorItems = populated.floorItems;
    state.floorTraps = populated.floorTraps;
    state.lastFootNoticeId = null;

    recordTrail();

    addLog(`B${floorNum}に到着した。`);
}

export function resetGame() {
    state.player.reset();
    resetIdentification();
    assignDisguises();
    state.floorNumber = 1;
    state.trailSet = new Set();
    state.trailOrder = [];
    state.logLines = [];
    state.menuStack = [];
    state.showMinimap = false;
    state.isTurnModeOnly = false;
    state.gameOverInfo = null;
    initFloor(1);
    state.gameState = GameState.INPUT_WAIT;
}

function recordTrail() {
    const key = tileKey(state.player.x, state.player.y);
    if (!state.trailSet.has(key)) {
        state.trailSet.add(key);
        state.trailOrder.push({ x: state.player.x, y: state.player.y });
    }
}

// =====================================================================
// --- 戦闘処理 ---
// =====================================================================
function attackMonster(monster) {
    const missChance = state.player.statusEffects.blind > 0 ? 0.3 : 0.05;
    if (Math.random() < missChance) {
        addLog(`${monster.name}への攻撃は外れた！`);
        return;
    }
    const atk = state.player.getAtk();
    const dmg = Math.max(1, atk - Math.floor(monster.def / 2) + randInt(-2, 2));
    monster.hp -= dmg;
    addLog(`${monster.name}に${dmg}のダメージ！`);
    if (monster.hp <= 0) {
        addLog(`${monster.name}を倒した！`);
        state.player.gainExp(monster.expValue, addLog);
    }
}

function applyThrowEffect(item, monster) {
    if (item.category === 'weapon') {
        const dmg = weaponTypes[item.typeIndex].atk + (item.enchant || 0) + 2;
        monster.hp -= dmg;
        addLog(`投げた${weaponTypes[item.typeIndex].name}が${monster.name}に${dmg}のダメージ！`);
    } else if (item.category === 'shield') {
        const dmg = shieldTypes[item.typeIndex].def + 2;
        monster.hp -= dmg;
        addLog(`投げた${shieldTypes[item.typeIndex].name}が${monster.name}に当たった！`);
    } else if (item.category === 'herb') {
        const t = herbTypes[item.typeIndex];
        t.identified = true;
        switch (t.effect) {
            case 'poison':
                monster.poisonTurns = Math.max(monster.poisonTurns, 6);
                addLog(`${monster.name}は${t.name}を浴びて毒状態になった！`);
                break;
            case 'blind':
                monster.hp -= 3;
                addLog(`${monster.name}に${t.name}が当たった！`);
                break;
            case 'heal':
            case 'fullheal':
                monster.hp = Math.min(monster.maxHp, monster.hp + 15);
                addLog(`しまった！${monster.name}を回復させてしまった！`);
                break;
            case 'strength':
                monster.atk += 2;
                addLog(`しまった！${monster.name}を強化してしまった！`);
                break;
            default:
                monster.hp -= 3;
        }
    } else if (item.category === 'scroll') {
        addLog('巻物を投げたが、特に何も起きなかった。');
    } else if (item.category === 'food') {
        monster.hp -= 2;
        addLog(`${monster.name}に食べ物が当たった。`);
    }

    if (monster.hp <= 0) {
        addLog(`${monster.name}を倒した！`);
        state.player.gainExp(monster.expValue, addLog);
    }
}

// =====================================================================
// --- タイルイベント（罠・足元アイテム通知・階段） ---
// =====================================================================
function checkTileEvents() {
    const trap = state.floorTraps.find(t => t.x === state.player.x && t.y === state.player.y);
    if (trap) {
        triggerTrap(trap, {
            player: state.player,
            grid: state.grid,
            monsters: state.monsters,
            floorItems: state.floorItems,
            floorTraps: state.floorTraps,
        }, addLog);
    }

    const fi = state.floorItems.find(f => f.x === state.player.x && f.y === state.player.y);
    if (fi) {
        if (state.lastFootNoticeId !== fi.item.id) {
            addLog(`ここに${getItemDisplayName(fi.item)}が落ちている。`);
            state.lastFootNoticeId = fi.item.id;
        }
    } else {
        state.lastFootNoticeId = null;
    }

    if (state.grid[state.player.y][state.player.x] === TILE_STAIRS) {
        addLog('階段を見つけた。次の階層へ進む。');
        state.pendingFloorChange = true;
        initFloor(state.floorNumber + 1);
        return;
    }

    recordTrail();
}

// =====================================================================
// --- ターン処理本体 ---
// =====================================================================
function waitAnimationComplete() {
    return new Promise(resolve => {
        function check() {
            let animating = state.player.isAnimating();
            state.monsters.forEach(m => { if (m.isAlive() && m.isAnimating()) animating = true; });
            if (!animating) resolve();
            else requestAnimationFrame(check);
        }
        check();
    });
}

function onPlayerDeath() {
    state.gameState = GameState.GAMEOVER;
    state.gameOverInfo = { floor: state.floorNumber, level: state.player.level };
    addLog('シレンは倒れた…（冒険終了）');
}

export async function handlePlayerAction(dx, dy) {
    if (state.gameState === GameState.AIM) {
        if (dx === 0 && dy === 0) cancelThrow();
        else await performThrow(dx, dy);
        return;
    }

    if (state.gameState !== GameState.INPUT_WAIT) return;
    if (state.player.isDead()) return;

    if (state.player.statusEffects.paralyzed > 0) {
        state.player.statusEffects.paralyzed--;
        addLog('体がしびれて動けない！');
        processMonsterAI(state.monsters, state.player, state.grid, MAP_WIDTH, MAP_HEIGHT, addLog);
        state.player.tickHungerAndStatus(addLog);
        if (state.player.isDead()) onPlayerDeath();
        return;
    }

    if (state.isTurnModeOnly && (dx !== 0 || dy !== 0)) {
        state.player.dirX = dx;
        state.player.dirY = dy;
        state.isTurnModeOnly = false;
        return;
    }

    state.gameState = GameState.ANIMATION;
    const targetX = state.player.x + dx;
    const targetY = state.player.y + dy;
    const targetMonster = state.monsters.find(m => m.isAlive() && m.x === targetX && m.y === targetY);

    if (targetMonster) {
        state.player.dirX = dx;
        state.player.dirY = dy;
        attackMonster(targetMonster);
    } else if (dx === 0 && dy === 0) {
        // 足踏み：その場でターンを消費するのみ
    } else if (
        targetX >= 0 && targetX < MAP_WIDTH && targetY >= 0 && targetY < MAP_HEIGHT &&
        state.grid[targetY][targetX] !== TILE_WALL
    ) {
        state.player.x = targetX;
        state.player.y = targetY;
        state.player.dirX = dx;
        state.player.dirY = dy;
    } else {
        // 壁：移動不可。ターンは消費しない。
        state.gameState = GameState.INPUT_WAIT;
        return;
    }

    await waitAnimationComplete();

    state.pendingFloorChange = false;
    checkTileEvents();
    if (state.pendingFloorChange) {
        state.pendingFloorChange = false;
        state.gameState = GameState.INPUT_WAIT;
        return;
    }

    processMonsterAI(state.monsters, state.player, state.grid, MAP_WIDTH, MAP_HEIGHT, addLog);
    await waitAnimationComplete();
    state.player.tickHungerAndStatus(addLog);

    if (state.player.isDead()) {
        onPlayerDeath();
        return;
    }
    state.gameState = GameState.INPUT_WAIT;
}

// =====================================================================
// --- 投げる（AIM状態） ---
// =====================================================================
export function startThrow(idx) {
    state.pendingThrowIdx = idx;
    state.menuStack = [];
    state.gameState = GameState.AIM;
    addLog('どの方向に投げる？(中央ボタンで取消)');
}

export function cancelThrow() {
    state.pendingThrowIdx = null;
    state.gameState = GameState.INPUT_WAIT;
    addLog('投げるのをやめた。');
}

export async function performThrow(dx, dy) {
    const idx = state.pendingThrowIdx;
    const item = state.player.inventory[idx];
    state.pendingThrowIdx = null;
    if (!item) {
        state.gameState = GameState.INPUT_WAIT;
        return;
    }
    state.gameState = GameState.ANIMATION;

    let x = state.player.x, y = state.player.y;
    let hitMonster = null;
    for (let step = 0; step < 12; step++) {
        x += dx; y += dy;
        if (x < 0 || y < 0 || x >= MAP_WIDTH || y >= MAP_HEIGHT || state.grid[y][x] === TILE_WALL) break;
        const m = state.monsters.find(mm => mm.isAlive() && mm.x === x && mm.y === y);
        if (m) { hitMonster = m; break; }
    }

    if (hitMonster) applyThrowEffect(item, hitMonster);
    else addLog(`${getItemDisplayName(item)}を投げたが、何にも当たらなかった。`);

    state.player.removeItemAt(idx);

    processMonsterAI(state.monsters, state.player, state.grid, MAP_WIDTH, MAP_HEIGHT, addLog);
    state.player.tickHungerAndStatus(addLog);

    if (state.player.isDead()) {
        onPlayerDeath();
        return;
    }
    state.gameState = GameState.INPUT_WAIT;
}

// =====================================================================
// --- Canvas内ポップアップメニュー ---
// =====================================================================
function buildRootRows() {
    const rows = [];
    const footItem = state.floorItems.find(fi => fi.x === state.player.x && fi.y === state.player.y);
    if (footItem) {
        rows.push({ label: `あしもと: ${getItemDisplayName(footItem.item)}`, action: () => openFootMenu(footItem) });
    }
    state.player.inventory.forEach((item, idx) => {
        const isEquipped = state.player.equippedWeapon === item || state.player.equippedShield === item;
        const label = (isEquipped ? '[装備] ' : '') + getItemDisplayName(item);
        rows.push({ label, action: () => openItemActionsMenu(idx) });
    });
    if (state.player.inventory.length === 0 && !footItem) {
        rows.push({ label: '（持ち物は空っぽだ）', action: () => {} });
    }
    rows.push({ label: 'とじる', action: () => closeMenu() });
    return rows;
}

function pushMenuScreen(title, rows) {
    state.menuStack.push({ title, cursor: 0, rows });
}

function rebuildToRoot() {
    state.menuStack = [];
    pushMenuScreen('メニュー', buildRootRows());
}

export function openMenu() {
    if (state.gameState !== GameState.INPUT_WAIT) return;
    state.gameState = GameState.MENU;
    rebuildToRoot();
}

export function closeMenu() {
    state.menuStack = [];
    state.gameState = GameState.INPUT_WAIT;
}

export function menuCancel() {
    if (state.menuStack.length <= 1) {
        closeMenu();
        return;
    }
    state.menuStack.pop();
}

export function menuNavigate(delta) {
    const top = state.menuStack[state.menuStack.length - 1];
    if (!top || top.rows.length === 0) return;
    top.cursor = (top.cursor + delta + top.rows.length) % top.rows.length;
}

export function menuDecide() {
    const top = state.menuStack[state.menuStack.length - 1];
    if (!top || top.rows.length === 0) return;
    const row = top.rows[top.cursor];
    if (row && typeof row.action === 'function') row.action();
}

function openFootMenu(footItem) {
    const rows = [];
    rows.push({ label: '拾う', action: () => pickUpFootItem(footItem) });
    if (footItem.item.category === 'food') {
        rows.push({ label: '食べる', action: () => eatFootItem(footItem) });
    }
    rows.push({ label: 'もどる', action: () => { state.menuStack.pop(); } });
    pushMenuScreen('あしもと', rows);
}

function pickUpFootItem(footItem) {
    const ok = state.player.pickUpItem(footItem.item, addLog);
    if (ok) {
        const idx = state.floorItems.indexOf(footItem);
        if (idx !== -1) state.floorItems.splice(idx, 1);
        state.lastFootNoticeId = null;
    }
    rebuildToRoot();
}

function eatFootItem(footItem) {
    state.player.eatFoodItemEffect(footItem.item, addLog);
    const idx = state.floorItems.indexOf(footItem);
    if (idx !== -1) state.floorItems.splice(idx, 1);
    state.lastFootNoticeId = null;
    rebuildToRoot();
}

function handleUseScroll(idx) {
    const result = state.player.useScrollAt(idx, addLog);
    if (result === 'teleport') {
        const pos = randomFreeTile(state.grid, state.player, state.monsters, state.floorItems, state.floorTraps);
        if (pos) {
            state.player.warpTo(pos.x, pos.y);
            addLog('見知らぬ場所に移動した！');
        }
    }
    rebuildToRoot();
}

function openItemActionsMenu(idx) {
    const item = state.player.inventory[idx];
    if (!item) {
        rebuildToRoot();
        return;
    }
    const isEquipped = state.player.equippedWeapon === item || state.player.equippedShield === item;
    const rows = [];

    if (item.category === 'weapon') {
        rows.push({ label: isEquipped ? '外す' : '装備', action: () => { state.player.toggleEquipWeapon(idx, addLog); rebuildToRoot(); } });
    } else if (item.category === 'shield') {
        rows.push({ label: isEquipped ? '外す' : '装備', action: () => { state.player.toggleEquipShield(idx, addLog); rebuildToRoot(); } });
    } else if (item.category === 'herb') {
        rows.push({ label: '飲む', action: () => { state.player.useHerbAt(idx, addLog); rebuildToRoot(); } });
    } else if (item.category === 'scroll') {
        rows.push({ label: '読む', action: () => handleUseScroll(idx) });
    } else if (item.category === 'food') {
        rows.push({ label: '食べる', action: () => { state.player.eatFoodAt(idx, addLog); rebuildToRoot(); } });
    }

    rows.push({ label: '投げる', action: () => startThrow(idx) });
    rows.push({ label: '捨てる', action: () => { state.player.dropItemAt(idx, addLog); rebuildToRoot(); } });
    rows.push({ label: 'もどる', action: () => { state.menuStack.pop(); } });

    pushMenuScreen(getItemDisplayName(item), rows);
}

// =====================================================================
// --- その他のトグル操作 ---
// =====================================================================
export function toggleTurnMode(forceVal) {
    if (state.gameState !== GameState.INPUT_WAIT) return;
    state.isTurnModeOnly = forceVal !== undefined ? forceVal : !state.isTurnModeOnly;
}

export function toggleMinimap(forceVal) {
    state.showMinimap = forceVal !== undefined ? forceVal : !state.showMinimap;
}

// ゲームオーバー画面からのリトライ
export function retryGame() {
    if (state.gameState !== GameState.GAMEOVER) return;
    resetGame();
}
