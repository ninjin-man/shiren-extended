// =====================================================================
// js/engine/input.js
// キーボードおよびモバイルタッチ（touchstart）入力を統合し、
// 現在のゲーム状態(state.gameState)に応じて適切な game.js の関数へ
// ディスパッチする。タッチ遅延対策として touchstart 時点で
// preventDefault() し、300ms遅延の発生するクリックイベントには頼らない。
// =====================================================================

import { GameState } from '../config/constants.js';
import {
    state,
    handlePlayerAction,
    openMenu,
    menuCancel,
    menuNavigate,
    menuDecide,
    toggleTurnMode,
    toggleMinimap,
    retryGame,
} from './game.js';

// パッドからの入力(dx, dy)を、現在のゲーム状態に応じて振り分ける
function dispatchDirectional(dx, dy) {
    switch (state.gameState) {
        case GameState.INPUT_WAIT:
        case GameState.AIM:
            handlePlayerAction(dx, dy);
            break;
        case GameState.MENU:
            if (dy === -1) menuNavigate(-1);
            else if (dy === 1) menuNavigate(1);
            else if (dx === 0 && dy === 0) menuDecide();
            break;
        case GameState.GAMEOVER:
            if (dx === 0 && dy === 0) retryGame();
            break;
        default:
            // ANIMATION中は入力を受け付けない
            break;
    }
}

function handleMenuButton() {
    if (state.gameState === GameState.INPUT_WAIT) {
        openMenu();
    } else if (state.gameState === GameState.MENU) {
        menuCancel();
    }
}

function handleTurnModeButton() {
    if (state.gameState === GameState.INPUT_WAIT) {
        toggleTurnMode();
    }
}

function handleMinimapButton() {
    if (state.gameState !== GameState.GAMEOVER) {
        toggleMinimap();
    }
}

export function initInput() {
    // --- バーチャルパッド（3x3） ---
    const padGrid = document.getElementById('pad-grid');
    const padButtons = document.querySelectorAll('.pad-btn');
    padButtons.forEach(btn => {
        const dx = parseInt(btn.getAttribute('data-dx'), 10);
        const dy = parseInt(btn.getAttribute('data-dy'), 10);
        const fire = (e) => {
            e.preventDefault();
            dispatchDirectional(dx, dy);
        };
        btn.addEventListener('touchstart', fire, { passive: false });
        btn.addEventListener('mousedown', fire);
    });

    // --- ユーティリティボタン ---
    const menuBtn = document.getElementById('menu-btn');
    menuBtn.addEventListener('touchstart', (e) => { e.preventDefault(); handleMenuButton(); }, { passive: false });
    menuBtn.addEventListener('mousedown', handleMenuButton);

    const turnBtn = document.getElementById('turn-mode-btn');
    turnBtn.addEventListener('touchstart', (e) => { e.preventDefault(); handleTurnModeButton(); }, { passive: false });
    turnBtn.addEventListener('mousedown', handleTurnModeButton);

    const minimapBtn = document.getElementById('minimap-btn');
    minimapBtn.addEventListener('touchstart', (e) => { e.preventDefault(); handleMinimapButton(); }, { passive: false });
    minimapBtn.addEventListener('mousedown', handleMinimapButton);

    // 状態に応じたボタン／パッドの見た目の更新（毎フレーム監視）
    const observer = () => {
        padGrid.classList.toggle('aim-mode', state.gameState === GameState.AIM);
        padGrid.classList.toggle('menu-mode', state.gameState === GameState.MENU || state.gameState === GameState.GAMEOVER);
        menuBtn.classList.toggle('active', state.gameState === GameState.MENU);
        turnBtn.classList.toggle('active', state.isTurnModeOnly);
        minimapBtn.classList.toggle('active', state.showMinimap);
        requestAnimationFrame(observer);
    };
    requestAnimationFrame(observer);

    // --- キーボード操作（デスクトップ確認用） ---
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Shift') { toggleTurnMode(true); return; }
        if (e.key === 'Tab' || e.key === 'g' || e.key === 'G') { e.preventDefault(); handleMinimapButton(); return; }
        if (e.key === 'm' || e.key === 'M' || e.key === 'Enter') { handleMenuButton(); return; }
        if (e.key === 'Escape') {
            if (state.gameState === GameState.MENU) menuCancel();
            else if (state.gameState === GameState.AIM) dispatchDirectional(0, 0);
            return;
        }

        let dx = 0, dy = 0;
        switch (e.key) {
            case 'ArrowUp': dy = -1; break;
            case 'ArrowDown': dy = 1; break;
            case 'ArrowLeft': dx = -1; break;
            case 'ArrowRight': dx = 1; break;
            case ' ': dx = 0; dy = 0; break;
            default: return;
        }
        e.preventDefault();
        dispatchDirectional(dx, dy);
    });
}
