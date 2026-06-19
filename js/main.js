// =====================================================================
// js/main.js
// ゲームの起動・全体初期化・メインループ（requestAnimationFrame）の管理。
// Canvasの実ピクセルサイズをここで確定し、ゲーム状態の初期化(resetGame)と
// 入力ハンドラの登録(initInput)を行ったうえで、毎フレームの描画ループを開始する。
// =====================================================================

import { CANVAS_WIDTH, CANVAS_HEIGHT, render } from './ui/renderer.js';
import { resetGame } from './engine/game.js';
import { initInput } from './engine/input.js';

function boot() {
    const canvas = document.getElementById('gameCanvas');
    canvas.width = CANVAS_WIDTH;
    canvas.height = CANVAS_HEIGHT;
    const ctx = canvas.getContext('2d');

    resetGame();
    initInput();

    function loop() {
        render(ctx);
        requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
}

boot();
