// =====================================================================
// js/entities/entity.js
// すべてのキャラクター（プレイヤー・モンスター）の基底クラス。
// 論理座標(x, y)と、なめらかな移動を表現する描画座標(renderX, renderY)を
// 分離して保持し、毎フレーム updateAnimation() で描画座標を論理座標へ
// 線形補間（Lerp）させることで、グリッドベースのターン制移動を
// 滑らかなアニメーションとして表現する。
// =====================================================================

import { TILE_SIZE } from '../config/constants.js';

// 補間係数。大きいほど追従が速い（=アニメーションが短い）。
const LERP_FACTOR = 0.3;
// これより小さい誤差になったら、ぴったり目的地に揃えて補間を打ち切る。
const SNAP_EPSILON = 0.1;

export class Entity {
    constructor(x, y, color, name) {
        this.x = x;
        this.y = y;
        this.renderX = x * TILE_SIZE;
        this.renderY = y * TILE_SIZE;
        this.color = color;
        this.name = name;

        // 直前に向いていた方向（描画・攻撃方向の表示に使用）
        this.dirX = 0;
        this.dirY = 1;

        this.hp = 1;
        this.maxHp = 1;
    }

    // 論理座標(x, y)に向かって描画座標を滑らかに近づける。毎フレーム呼ぶ。
    updateAnimation() {
        const targetX = this.x * TILE_SIZE;
        const targetY = this.y * TILE_SIZE;
        this.renderX += (targetX - this.renderX) * LERP_FACTOR;
        this.renderY += (targetY - this.renderY) * LERP_FACTOR;
        if (Math.abs(this.renderX - targetX) < SNAP_EPSILON) this.renderX = targetX;
        if (Math.abs(this.renderY - targetY) < SNAP_EPSILON) this.renderY = targetY;
    }

    // 描画座標がまだ論理座標に追いついていない（アニメーション中）かどうか。
    isAnimating() {
        return this.renderX !== this.x * TILE_SIZE || this.renderY !== this.y * TILE_SIZE;
    }

    // 瞬間移動（罠・巻物のワープ等）。アニメーションを挟まずに即座に座標を合わせる。
    warpTo(x, y) {
        this.x = x;
        this.y = y;
        this.renderX = x * TILE_SIZE;
        this.renderY = y * TILE_SIZE;
    }
}
