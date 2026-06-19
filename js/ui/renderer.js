// =====================================================================
// js/ui/renderer.js
// すべての描画をCanvas内部だけで完結させる。
// ・地形／階段／罠／アイテム／モンスター／プレイヤー（視界制限つき）
// ・最上部に統合ステータス（実機風フォント＋黒縁ドロップシャドウ）とログ
// ・紺色＋二重白縁のクラシックなポップアップウィンドウ（メニュー／ゲームオーバー）
// ・トグル式ミニマップ（軌跡＝白、敵＝赤、アイテム＝青）
// ・カメラ（プレイヤー追従スクロール）
// HTML側には一切のステータス表示・ログ・オーバーレイ要素を置かない。
// =====================================================================

import {
    TILE_SIZE,
    VIEW_COLS,
    VIEW_ROWS,
    HUD_HEIGHT,
    MAP_WIDTH,
    MAP_HEIGHT,
    TILE_WALL,
    TILE_STAIRS,
    GameState,
    ITEM_ICON_COLOR,
    tileKey,
} from '../config/constants.js';
import { computeVisibleTiles, computeCamera } from '../engine/map.js';
import { state } from '../engine/game.js';

export const CANVAS_WIDTH = VIEW_COLS * TILE_SIZE;
export const CANVAS_HEIGHT = HUD_HEIGHT + VIEW_ROWS * TILE_SIZE;

// =====================================================================
// --- テキスト描画ヘルパー（白文字＋黒縁ドロップシャドウ＝実機風） ---
// =====================================================================
function drawShadowText(ctx, text, x, y, font, color) {
    ctx.font = font;
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = '#000000';
    ctx.fillText(text, x + 1, y + 1);
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
}

function pad2(n) {
    return String(Math.max(0, n)).padStart(2, '0');
}

function padNum(n, width) {
    return String(Math.max(0, n)).padStart(width, ' ');
}

// =====================================================================
// --- 地形・キャラクターの描画（視界制限つき） ---
// =====================================================================
function drawWorld(ctx, camX, camY, visible) {
    // 背景は常に漆黒
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, HUD_HEIGHT, CANVAS_WIDTH, VIEW_ROWS * TILE_SIZE);

    // 地形タイル
    for (let vy = 0; vy < VIEW_ROWS; vy++) {
        for (let vx = 0; vx < VIEW_COLS; vx++) {
            const wx = camX + vx;
            const wy = camY + vy;
            if (wx < 0 || wy < 0 || wx >= MAP_WIDTH || wy >= MAP_HEIGHT) continue;
            if (!visible.has(tileKey(wx, wy))) continue;

            const tile = state.grid[wy][wx];
            const sx = vx * TILE_SIZE;
            const sy = HUD_HEIGHT + vy * TILE_SIZE;

            if (tile === TILE_WALL) ctx.fillStyle = '#444446';
            else if (tile === TILE_STAIRS) ctx.fillStyle = '#665500';
            else ctx.fillStyle = '#222225';
            ctx.fillRect(sx, sy, TILE_SIZE - 1, TILE_SIZE - 1);
        }
    }

    // 階段マーク（視界内のみ）
    if (visible.has(tileKey(state.stairsPos.x, state.stairsPos.y))) {
        const sx = (state.stairsPos.x - camX) * TILE_SIZE;
        const sy = HUD_HEIGHT + (state.stairsPos.y - camY) * TILE_SIZE;
        if (state.stairsPos.x - camX >= 0 && state.stairsPos.x - camX < VIEW_COLS &&
            state.stairsPos.y - camY >= 0 && state.stairsPos.y - camY < VIEW_ROWS) {
            ctx.fillStyle = '#ffcc00';
            ctx.font = '20px sans-serif';
            ctx.textBaseline = 'alphabetic';
            ctx.fillText('階', sx + 6, sy + 24);
        }
    }

    // 発見済みの罠（視界内のみ）
    state.floorTraps.forEach(trap => {
        if (!trap.revealed) return;
        if (!visible.has(tileKey(trap.x, trap.y))) return;
        const vx = trap.x - camX, vy = trap.y - camY;
        if (vx < 0 || vx >= VIEW_COLS || vy < 0 || vy >= VIEW_ROWS) return;
        const cx = vx * TILE_SIZE, cy = HUD_HEIGHT + vy * TILE_SIZE;
        ctx.strokeStyle = '#ff3333';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(cx + 6, cy + 6); ctx.lineTo(cx + TILE_SIZE - 6, cy + TILE_SIZE - 6);
        ctx.moveTo(cx + TILE_SIZE - 6, cy + 6); ctx.lineTo(cx + 6, cy + TILE_SIZE - 6);
        ctx.stroke();
    });

    // 床のアイテム（視界内のみ）
    state.floorItems.forEach(fi => {
        if (!visible.has(tileKey(fi.x, fi.y))) return;
        const vx = fi.x - camX, vy = fi.y - camY;
        if (vx < 0 || vx >= VIEW_COLS || vy < 0 || vy >= VIEW_ROWS) return;
        const cx = vx * TILE_SIZE + TILE_SIZE / 2;
        const cy = HUD_HEIGHT + vy * TILE_SIZE + TILE_SIZE / 2;
        ctx.fillStyle = ITEM_ICON_COLOR[fi.item.category] || '#ffffff';
        if (fi.item.category === 'herb' || fi.item.category === 'food') {
            ctx.beginPath();
            ctx.arc(cx, cy, 7, 0, Math.PI * 2);
            ctx.fill();
        } else {
            ctx.fillRect(cx - 7, cy - 7, 14, 14);
        }
    });

    // モンスター（視界内のみ）
    state.monsters.forEach(monster => {
        if (!monster.isAlive()) return;
        const wx = Math.round(monster.renderX / TILE_SIZE);
        const wy = Math.round(monster.renderY / TILE_SIZE);
        if (!visible.has(tileKey(monster.x, monster.y)) && !visible.has(tileKey(wx, wy))) return;
        const sx = monster.renderX - camX * TILE_SIZE;
        const sy = HUD_HEIGHT + monster.renderY - camY * TILE_SIZE;
        if (sx < -TILE_SIZE || sx > CANVAS_WIDTH || sy < HUD_HEIGHT - TILE_SIZE || sy > CANVAS_HEIGHT) return;

        ctx.fillStyle = monster.color;
        ctx.fillRect(sx + 4, sy + 4, TILE_SIZE - 8, TILE_SIZE - 8);

        // HPバー
        ctx.fillStyle = '#000';
        ctx.fillRect(sx, sy - 6, TILE_SIZE, 4);
        ctx.fillStyle = '#0f0';
        ctx.fillRect(sx, sy - 6, TILE_SIZE * Math.max(0, monster.hp / monster.maxHp), 4);
    });

    // プレイヤー（常時描画。カメラはプレイヤーを常にビューポート内に収める）
    const psx = state.player.renderX - camX * TILE_SIZE;
    const psy = HUD_HEIGHT + state.player.renderY - camY * TILE_SIZE;
    ctx.fillStyle = state.player.color;
    ctx.fillRect(psx + 2, psy + 2, TILE_SIZE - 4, TILE_SIZE - 4);

    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(psx + TILE_SIZE / 2, psy + TILE_SIZE / 2);
    ctx.lineTo(psx + TILE_SIZE / 2 + state.player.dirX * 12, psy + TILE_SIZE / 2 + state.player.dirY * 12);
    ctx.stroke();
}

// =====================================================================
// --- HUD（ステータス＋ログ）：Canvas最上部に統合描画 ---
// =====================================================================
function drawHud(ctx) {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.55)';
    ctx.fillRect(0, 0, CANVAS_WIDTH, HUD_HEIGHT);

    const p = state.player;
    const hpRatio = p.hp / p.maxHp;
    const hpColor = hpRatio <= 0.3 ? '#ff5555' : '#ffffff';
    const satietyRatio = p.satiety / p.maxSatiety;
    const satietyColor = satietyRatio <= 0.3 ? '#ff8855' : '#ffffff';

    const statusFont = 'bold 14px sans-serif';
    let x = 6;
    const y = 17;

    const segments = [
        { text: `${state.floorNumber}F`, color: '#ffffff' },
        { text: `  Lv ${pad2(p.level)}`, color: '#ffffff' },
        { text: `  HP `, color: '#ffffff' },
        { text: `${padNum(Math.max(0, p.hp), 2)}/${padNum(p.maxHp, 2)}`, color: hpColor },
        { text: `  満腹度 `, color: '#ffffff' },
        { text: `${Math.round(satietyRatio * 100)}%`, color: satietyColor },
    ];
    ctx.font = statusFont;
    segments.forEach(seg => {
        drawShadowText(ctx, seg.text, x, y, statusFont, seg.color);
        x += ctx.measureText(seg.text).width;
    });

    // 攻撃力・防御力（2段目左寄せ）
    const statLine = `攻 ${p.getAtk()}　防 ${p.getDef()}`;
    drawShadowText(ctx, statLine, 6, 32, '11px sans-serif', '#ffdd55');

    // インラインログ（最大2行・右寄せエリアでなく状態行の下に）
    const logFont = '11px sans-serif';
    state.logLines.forEach((line, i) => {
        drawShadowText(ctx, line, 92, 21 + i * 12, logFont, '#55ff88');
    });
}

// =====================================================================
// --- Canvas内ポップアップウィンドウ（紺色＋二重白縁） ---
// =====================================================================
function drawPopupPanel(ctx, title, infoLines, rows, cursorIndex) {
    // 背景を少し暗くして注意を引く
    ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    const rowHeight = 20;
    const innerPadding = 10;
    const titleHeight = 22;
    const infoHeight = infoLines.length * 14;
    const rowsHeight = rows.length * rowHeight;
    const panelW = Math.min(CANVAS_WIDTH - 24, 280);
    const panelH = Math.min(CANVAS_HEIGHT - 16, titleHeight + infoHeight + rowsHeight + innerPadding * 2);
    const panelX = (CANVAS_WIDTH - panelW) / 2;
    const panelY = (CANVAS_HEIGHT - panelH) / 2;

    // 紺色の塗り
    ctx.fillStyle = '#161650';
    ctx.fillRect(panelX, panelY, panelW, panelH);

    // 二重の白縁
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.strokeRect(panelX + 1, panelY + 1, panelW - 2, panelH - 2);
    ctx.strokeRect(panelX + 5, panelY + 5, panelW - 10, panelH - 10);

    // タイトル
    drawShadowText(ctx, title, panelX + innerPadding, panelY + 20, 'bold 14px sans-serif', '#ffdd55');

    // 情報行（ゲームオーバー時の到達階層など）
    let cursorY = panelY + titleHeight + 6;
    infoLines.forEach(line => {
        drawShadowText(ctx, line, panelX + innerPadding, cursorY, '12px sans-serif', '#ffffff');
        cursorY += 14;
    });

    // 選択可能な行
    rows.forEach((row, i) => {
        const ry = cursorY + i * rowHeight + 12;
        const isSelected = i === cursorIndex;
        const prefix = isSelected ? '▶ ' : '　';
        const color = isSelected ? '#ffee55' : '#ffffff';
        if (isSelected) {
            ctx.fillStyle = 'rgba(255, 255, 255, 0.12)';
            ctx.fillRect(panelX + 6, ry - 13, panelW - 12, rowHeight);
        }
        drawShadowText(ctx, prefix + row.label, panelX + innerPadding, ry, '13px sans-serif', color);
    });
}

function drawMenuOverlay(ctx) {
    const top = state.menuStack[state.menuStack.length - 1];
    if (!top) return;
    drawPopupPanel(ctx, top.title, [], top.rows, top.cursor);
}

function drawGameOverOverlay(ctx) {
    const info = state.gameOverInfo || { floor: state.floorNumber, level: state.player.level };
    drawPopupPanel(
        ctx,
        'シレンは倒れた…',
        [`到達階層 B${info.floor}　Lv.${info.level}`],
        [{ label: 'もう一度挑む（中央ボタンで決定）' }],
        0
    );
}

// =====================================================================
// --- ミニマップ（トグル式オーバーレイ：軌跡＝白、敵＝赤、アイテム＝青） ---
// =====================================================================
function drawMinimap(ctx) {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.78)';
    ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    const margin = 14;
    const availW = CANVAS_WIDTH - margin * 2;
    const availH = CANVAS_HEIGHT - margin * 2;
    const scale = Math.min(availW / MAP_WIDTH, availH / MAP_HEIGHT);
    const offsetX = (CANVAS_WIDTH - MAP_WIDTH * scale) / 2;
    const offsetY = (CANVAS_HEIGHT - MAP_HEIGHT * scale) / 2;

    const toScreen = (wx, wy) => ({
        x: offsetX + wx * scale,
        y: offsetY + wy * scale,
    });

    // 軌跡（白い細線＋点）
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    state.trailOrder.forEach((p, i) => {
        const s = toScreen(p.x + 0.5, p.y + 0.5);
        if (i === 0) ctx.moveTo(s.x, s.y);
        else ctx.lineTo(s.x, s.y);
    });
    ctx.stroke();

    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
    state.trailOrder.forEach(p => {
        const s = toScreen(p.x + 0.5, p.y + 0.5);
        ctx.fillRect(s.x - 1, s.y - 1, 2, 2);
    });

    // 階段（黄）
    const stairS = toScreen(state.stairsPos.x + 0.5, state.stairsPos.y + 0.5);
    ctx.fillStyle = '#ffcc00';
    ctx.fillRect(stairS.x - 2, stairS.y - 2, 4, 4);

    // アイテム（青）
    ctx.fillStyle = '#5599ff';
    state.floorItems.forEach(fi => {
        const s = toScreen(fi.x + 0.5, fi.y + 0.5);
        ctx.beginPath();
        ctx.arc(s.x, s.y, 2.5, 0, Math.PI * 2);
        ctx.fill();
    });

    // 敵（赤）
    ctx.fillStyle = '#ff4444';
    state.monsters.forEach(m => {
        if (!m.isAlive()) return;
        const s = toScreen(m.x + 0.5, m.y + 0.5);
        ctx.beginPath();
        ctx.arc(s.x, s.y, 2.5, 0, Math.PI * 2);
        ctx.fill();
    });

    // 自キャラ（白・大きめ）
    const ps = toScreen(state.player.x + 0.5, state.player.y + 0.5);
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(ps.x, ps.y, 4, 0, Math.PI * 2);
    ctx.fill();

    drawShadowText(ctx, '全体図', 8, CANVAS_HEIGHT - 8, 'bold 12px sans-serif', '#ffffff');
}

// =====================================================================
// --- メインの描画エントリーポイント ---
// =====================================================================
export function render(ctx) {
    // アニメーション補間の更新
    state.player.updateAnimation();
    state.monsters.forEach(m => { if (m.isAlive()) m.updateAnimation(); });

    ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    const { camX, camY } = computeCamera(state.player);
    const visible = computeVisibleTiles(state.player, state.rooms);

    drawWorld(ctx, camX, camY, visible);
    drawHud(ctx);

    if (state.gameState === GameState.MENU) {
        drawMenuOverlay(ctx);
    } else if (state.gameState === GameState.GAMEOVER) {
        drawGameOverOverlay(ctx);
    }

    if (state.showMinimap && state.gameState !== GameState.GAMEOVER) {
        drawMinimap(ctx);
    }
}
