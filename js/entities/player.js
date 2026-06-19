// =====================================================================
// js/entities/player.js
// プレイヤー（シレン）固有のロジックを集約する。
// ・レベル/経験値/HP/攻防・満腹度（ハラヘリ：10ターンで1減少）
// ・持ち物の追加／削除、武器・盾の着脱
// ・草／巻物／食料（おにぎり）の使用（足元から直接食べる処理も含む）
// マップやモンスター配列など他モジュールの状態には一切触れず、
// 必要な場合は呼び出し側（engine/game.js）から戻り値で合図を返す
// （例：巻物のテレポートは 'teleport' という文字列を返すだけに留める）。
// =====================================================================

import { Entity } from './entity.js';
import {
    MAX_INV,
    weaponTypes,
    shieldTypes,
    herbTypes,
    scrollTypes,
    foodTypes,
    getItemDisplayName,
    isItemFullyIdentified,
    identifyItem,
} from '../config/constants.js';

// 何ターンごとに満腹度が1減るか
const HUNGER_INTERVAL = 10;

export class Player extends Entity {
    constructor() {
        super(0, 0, '#00ffcc', 'シレン');
        this.reset();
    }

    reset() {
        this.level = 1;
        this.exp = 0;
        this.expNext = 10;
        this.maxHp = 30;
        this.hp = 30;
        this.baseAtk = 5;
        this.baseDef = 2;
        this.satiety = 100;
        this.maxSatiety = 100;
        this.turnCounter = 0;
        this.inventory = [];
        this.equippedWeapon = null;
        this.equippedShield = null;
        this.statusEffects = { poison: 0, blind: 0, paralyzed: 0 };
        this.dirX = 0;
        this.dirY = 1;
    }

    // --- ステータス計算 ---
    getAtk() {
        let atk = this.baseAtk;
        if (this.equippedWeapon) {
            atk += weaponTypes[this.equippedWeapon.typeIndex].atk + (this.equippedWeapon.enchant || 0);
        }
        return atk;
    }

    getDef() {
        let def = this.baseDef;
        if (this.equippedShield) {
            def += shieldTypes[this.equippedShield.typeIndex].def + (this.equippedShield.enchant || 0);
        }
        return def;
    }

    isDead() {
        return this.hp <= 0;
    }

    takeDamage(amount) {
        this.hp -= amount;
    }

    // --- 経験値・レベルアップ ---
    gainExp(amount, addLog) {
        this.exp += amount;
        while (this.exp >= this.expNext) {
            this.exp -= this.expNext;
            this.level++;
            this.maxHp += 8;
            this.baseAtk += 2;
            this.baseDef += 1;
            this.hp = this.maxHp;
            this.expNext = Math.floor(this.expNext * 1.4) + 5;
            addLog(`レベルが上がった！ Lv.${this.level}になった。`);
        }
    }

    // --- 満腹度・状態異常の経過処理（1ターンにつき1回呼ぶ） ---
    tickHungerAndStatus(addLog) {
        this.turnCounter++;
        if (this.turnCounter % HUNGER_INTERVAL === 0) {
            const before = this.satiety;
            this.satiety = Math.max(0, this.satiety - 1);
            if (before > 30 && this.satiety <= 30) addLog('お腹が減ってきた…');
            if (before > 0 && this.satiety === 0) addLog('お腹がすいて力が出ない！');
        }
        if (this.satiety <= 0) this.hp -= 2;

        if (this.statusEffects.poison > 0) {
            this.hp -= 2;
            this.statusEffects.poison--;
            addLog('毒で体力が削られている…');
        }
        if (this.statusEffects.blind > 0) this.statusEffects.blind--;
    }

    // --- 持ち物管理 ---
    hasInventorySpace() {
        return this.inventory.length < MAX_INV;
    }

    pickUpItem(item, addLog) {
        if (!this.hasInventorySpace()) {
            addLog('持ち物がいっぱいで何も拾えなかった。');
            return false;
        }
        this.inventory.push(item);
        addLog(`${getItemDisplayName(item)}を手に入れた。`);
        return true;
    }

    // 持ち物からidxの要素を取り除いて返す。装備中であれば装備も解除する。
    removeItemAt(idx) {
        const item = this.inventory[idx];
        if (!item) return null;
        this.inventory.splice(idx, 1);
        if (this.equippedWeapon === item) this.equippedWeapon = null;
        if (this.equippedShield === item) this.equippedShield = null;
        return item;
    }

    dropItemAt(idx, addLog) {
        const item = this.inventory[idx];
        if (!item) return;
        addLog(`${getItemDisplayName(item)}を捨てた。`);
        this.removeItemAt(idx);
    }

    // --- 装備 ---
    toggleEquipWeapon(idx, addLog) {
        const item = this.inventory[idx];
        if (!item || item.category !== 'weapon') return;
        if (this.equippedWeapon === item) {
            this.equippedWeapon = null;
            addLog(`${getItemDisplayName(item)}を外した。`);
        } else {
            this.equippedWeapon = item;
            addLog(`${getItemDisplayName(item)}を装備した。`);
        }
    }

    toggleEquipShield(idx, addLog) {
        const item = this.inventory[idx];
        if (!item || item.category !== 'shield') return;
        if (this.equippedShield === item) {
            this.equippedShield = null;
            addLog(`${getItemDisplayName(item)}を外した。`);
        } else {
            this.equippedShield = item;
            addLog(`${getItemDisplayName(item)}を装備した。`);
        }
    }

    // --- 草を飲む ---
    useHerbAt(idx, addLog) {
        const item = this.inventory[idx];
        if (!item || item.category !== 'herb') return;
        const t = herbTypes[item.typeIndex];
        const wasIdentified = t.identified;
        t.identified = true;
        switch (t.effect) {
            case 'heal':
                this.hp = Math.min(this.maxHp, this.hp + 20);
                addLog(`${t.name}を飲んだ。HPが少し回復した。`);
                break;
            case 'fullheal':
                this.hp = this.maxHp;
                addLog(`${t.name}を飲んだ。HPが全回復した！`);
                break;
            case 'poison':
                this.statusEffects.poison = Math.max(this.statusEffects.poison, 6);
                addLog(`${t.name}を飲んだ。毒にやられた…`);
                break;
            case 'blind':
                this.statusEffects.blind = Math.max(this.statusEffects.blind, 6);
                addLog(`${t.name}を飲んだ。目が見えにくくなった…`);
                break;
            case 'strength':
                this.baseAtk += 1;
                addLog(`${t.name}を飲んだ。力が湧いてきた！(攻撃力+1)`);
                break;
        }
        if (!wasIdentified) addLog(`これは${t.name}だったのか！`);
        this.removeItemAt(idx);
    }

    // --- 巻物を読む ---
    // 戻り値: 'teleport' の場合のみ、呼び出し側(game.js)がマップを使って
    // ワープ先を決定し、player.warpTo() を呼ぶ必要がある。それ以外は null。
    useScrollAt(idx, addLog) {
        const item = this.inventory[idx];
        if (!item || item.category !== 'scroll') return null;
        const t = scrollTypes[item.typeIndex];
        const wasIdentified = t.identified;
        t.identified = true;
        let needsTeleport = false;

        switch (t.effect) {
            case 'identify': {
                const target = this.inventory.find(it => it !== item && !isItemFullyIdentified(it));
                if (target) {
                    identifyItem(target);
                    addLog(`${getItemDisplayName(target)}の正体が分かった！`);
                } else {
                    addLog('特に識別するものはなかった。');
                }
                break;
            }
            case 'enchant': {
                const w = this.equippedWeapon || this.inventory.find(it => it.category === 'weapon' && it !== item);
                if (w) {
                    w.enchant = (w.enchant || 0) + 1;
                    w.identified = true;
                    addLog(`${weaponTypes[w.typeIndex].name}が輝いた！（強化された）`);
                } else {
                    addLog('強化できる武器がなかった。');
                }
                break;
            }
            case 'teleport':
                needsTeleport = true;
                addLog('まばゆい光に包まれた！');
                break;
            case 'weaken': {
                const w = this.equippedWeapon;
                if (w) {
                    w.enchant = (w.enchant || 0) - 1;
                    addLog('武器が脆くなった気がする…');
                } else {
                    this.satiety = Math.max(0, this.satiety - 15);
                    addLog('嫌な予感がした…');
                }
                break;
            }
        }
        if (!wasIdentified) addLog(`これは${t.name}だったのか！`);
        this.removeItemAt(idx);
        return needsTeleport ? 'teleport' : null;
    }

    // --- 食料（おにぎり）を食べる：持ち物の中から ---
    eatFoodAt(idx, addLog) {
        const item = this.inventory[idx];
        if (!item || item.category !== 'food') return;
        this.eatFoodItemEffect(item, addLog);
        this.removeItemAt(idx);
    }

    // --- 食料を直接食べる効果適用のみ（持ち物からの削除は呼び出し側で行わない＝
    //     足元のアイテムを直接食べる場合は持ち物自体に入れないため、本メソッドのみ呼ぶ） ---
    eatFoodItemEffect(item, addLog) {
        const t = foodTypes[item.typeIndex];
        this.satiety = Math.min(this.maxSatiety, this.satiety + t.satiety);
        addLog(`${t.name}を食べた。満腹度が回復した。`);
    }
}
