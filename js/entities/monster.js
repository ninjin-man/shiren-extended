// =====================================================================
// js/entities/monster.js
// モンスターのインスタンス生成と、SFC版シレン準拠の8方向追尾AIを実装する。
// AIはプレイヤーとの差分(dx, dy)から8方向のうち最も近づける方向を選び、
// 壁にぶつかる場合は軸を1つだけ殺して迂回を試みる（完全な経路探索はしない
// 簡易追尾だが、実機の雑魚モンスターの挙動に近い）。
// =====================================================================

import { Entity } from './entity.js';
import { monsterTypes, TILE_WALL, randInt } from '../config/constants.js';

export class Monster extends Entity {
    constructor(typeIndex, x, y, floor) {
        const t = monsterTypes[typeIndex];
        super(x, y, t.color, t.name);
        this.typeIndex = typeIndex;
        this.maxHp = t.hp + floor * 2;
        this.hp = this.maxHp;
        this.atk = t.atk + floor;
        this.def = t.def + Math.floor(floor / 2);
        this.expValue = t.exp + floor;
        this.poisonTurns = 0;
    }

    isAlive() {
        return this.hp > 0;
    }
}

export function createMonster(typeIndex, x, y, floor) {
    return new Monster(typeIndex, x, y, floor);
}

// モンスター全体の行動（毒のダメージ進行 → 追尾移動 or プレイヤーへの攻撃）を1ターン分処理する。
// grid: 現在フロアの地形配列, mapWidth/mapHeight: マップサイズ
// addLog: ログ出力関数, player: Playerインスタンス（getDef()/takeDamage()/gainExp()を使用）
export function processMonsterAI(monsters, player, grid, mapWidth, mapHeight, addLog) {
    monsters.forEach(monster => {
        if (!monster.isAlive()) return;

        // 毒の進行
        if (monster.poisonTurns > 0) {
            monster.hp -= 2;
            monster.poisonTurns--;
            if (monster.hp <= 0) {
                addLog(`${monster.name}は毒で倒れた！`);
                player.gainExp(monster.expValue, addLog);
                return;
            }
        }

        const diffX = player.x - monster.x;
        const diffY = player.y - monster.y;
        let moveX = Math.sign(diffX);
        let moveY = Math.sign(diffY);

        let nextX = monster.x + moveX;
        let nextY = monster.y + moveY;

        const inBounds = (x, y) => x >= 0 && y >= 0 && x < mapWidth && y < mapHeight;

        if (!inBounds(nextX, nextY) || grid[nextY][nextX] === TILE_WALL) {
            // 斜め移動が壁に阻まれた場合、縦・横どちらか片方だけの移動を試みる
            if (inBounds(nextX, monster.y) && grid[monster.y][nextX] === 0 && !(nextX === player.x && monster.y === player.y)) {
                moveY = 0;
            } else if (inBounds(monster.x, nextY) && grid[nextY][monster.x] === 0 && !(monster.x === player.x && nextY === player.y)) {
                moveX = 0;
            } else {
                moveX = 0;
                moveY = 0;
            }
        }

        nextX = monster.x + moveX;
        nextY = monster.y + moveY;

        if (nextX === player.x && nextY === player.y) {
            // プレイヤーへの攻撃
            if (Math.random() < 0.1) {
                addLog(`${monster.name}の攻撃は外れた！`);
            } else {
                const dmg = Math.max(1, monster.atk - Math.floor(player.getDef() / 2) + randInt(-1, 2));
                player.takeDamage(dmg);
                addLog(`${monster.name}の攻撃！ ${dmg}のダメージを受けた。`);
            }
        } else if (moveX !== 0 || moveY !== 0) {
            const colliding = monsters.some(m => m !== monster && m.isAlive() && m.x === nextX && m.y === nextY);
            if (!colliding) {
                monster.x = nextX;
                monster.y = nextY;
                monster.dirX = moveX;
                monster.dirY = moveY;
            }
        }
    });
}
