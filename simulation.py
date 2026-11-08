from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random

# ---------------- Constants ---------------- #
APP_TITLE = "3D Zombie Shooter"
WORLD_SIZE = 64
PLAYER_MAX_HP = 100
ENEMY_HP = 60
ENEMY_DAMAGE = 10
BULLET_DAMAGE = 34
ENEMY_SPEED = 2
ENEMY_COUNT_BASE = 4
ENEMY_GROWTH = 1.35
MAG_SIZE = 12
FIRE_COOLDOWN = 0.12
RELOAD_TIME = 0.8
FOV_DEFAULT = 90
FOV_AIM = 60

# ---------------- Game Classes ---------------- #
class Enemy(Entity):
    def __init__(self, position=(0,0,0)):
        super().__init__(
            model='cube',
            color=color.red,
            scale=1.2,
            collider='box',
            position=position
        )
        self.hp = ENEMY_HP

    def update(self):
        if game.game_over or game.paused:
            return
        # Move toward player
        direction = (game.player.position - self.position).normalized()
        self.position += direction * ENEMY_SPEED * time.dt
        self.look_at(game.player.position)
        # Attack player if close
        if distance(self.position, game.player.position) < 1.5:
            game.damage_player(ENEMY_DAMAGE * time.dt)

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.die()

    def die(self):
        destroy(self)
        if self in game.enemies:
            game.enemies.remove(self)
        game.score += 10
        game.score_text.text = f"Score {game.score}"

class Projectile(Entity):
    def __init__(self, origin, direction, damage=BULLET_DAMAGE):
        super().__init__(model='sphere', scale=0.15, color=color.cyan, position=origin, collider='sphere')
        self.direction = direction
        self.speed = 50
        self.damage = damage
        self.life = 3

    def update(self):
        if game.game_over or game.paused:
            destroy(self)
            return
        self.position += self.direction * self.speed * time.dt
        self.life -= time.dt
        if self.life <= 0:
            destroy(self)
            return
        hit = self.intersects()
        if hit.hit:
            if isinstance(hit.entity, Enemy):
                hit.entity.take_damage(self.damage)
            destroy(self)

class Gun(Entity):
    def __init__(self):
        super().__init__(parent=camera.ui, model='quad', color=color.white10, scale=(.18,.1), position=(.18,-.2))
        self.ammo = MAG_SIZE
        self.mag_size = MAG_SIZE
        self.cooldown = 0
        self.reloading = False

    def update(self):
        self.cooldown = max(0, self.cooldown - time.dt)

    def shoot(self):
        if game.game_over or game.paused or self.reloading or self.cooldown > 0:
            return
        if self.ammo <= 0:
            self.reload()
            return
        self.ammo -= 1
        self.cooldown = FIRE_COOLDOWN
        origin = camera.world_position + camera.forward * 0.5
        Projectile(origin, camera.forward)

    def reload(self):
        if self.reloading or self.ammo == self.mag_size:
            return
        self.reloading = True
        invoke(self.finish_reload, delay=RELOAD_TIME)

    def finish_reload(self):
        self.ammo = self.mag_size
        self.reloading = False

# ---------------- Main Game ---------------- #
class Game(Entity):
    instance = None
    def __init__(self):
        super().__init__()
        Game.instance = self
        window.title = APP_TITLE

        # Environment
        self.ground = Entity(model='plane', scale=WORLD_SIZE, texture='white_cube', texture_scale=(WORLD_SIZE,WORLD_SIZE), collider='box', color=color.light_gray)
        wall_h = 4
        self.boundaries = [
            Entity(model='cube', scale=(WORLD_SIZE,wall_h,1), position=(0,wall_h/2,-WORLD_SIZE/2), color=color.gray, collider='box'),
            Entity(model='cube', scale=(WORLD_SIZE,wall_h,1), position=(0,wall_h/2,WORLD_SIZE/2), color=color.gray, collider='box'),
            Entity(model='cube', scale=(1,wall_h,WORLD_SIZE), position=(-WORLD_SIZE/2,wall_h/2,0), color=color.gray, collider='box'),
            Entity(model='cube', scale=(1,wall_h,WORLD_SIZE), position=(WORLD_SIZE/2,wall_h/2,0), color=color.gray, collider='box')
        ]

        # Player
        self.player = FirstPersonController(y=2, speed=7)
        self.player.cursor.enabled = False
        camera.fov = FOV_DEFAULT

        # Crosshair
        self.crosshair = Entity(parent=camera.ui, model='quad', color=color.black, scale=.008)

        # Gun
        self.gun = Gun()

        # HUD
        self.player_hp = PLAYER_MAX_HP
        self.score = 0
        self.wave = 0
        self.paused = False
        self.hp_bar_bg = Entity(parent=camera.ui, model='quad', color=color.rgba(0,0,0,140), scale=(.36,.03), position=(-.3,.45), origin_x=-.5)
        self.hp_bar = Entity(parent=self.hp_bar_bg, model='quad', color=color.azure, scale=(.36,.03), origin_x=-.5, x=-.18)
        self.ammo_text = Text(parent=camera.ui, text=f'{self.gun.ammo}/{self.gun.mag_size}', position=(.48,-.47))
        self.score_text = Text(parent=camera.ui, text=f'Score {self.score}', position=(-.5,.4))
        self.wave_text = Text(parent=camera.ui, text=f'Wave {self.wave}', position=(-.5,.45))
        self.toast = Text(parent=camera.ui, text='', position=(0,.35), origin=(0,0))
        self.lose_text = Text(parent=camera.ui, text='', color=color.red, scale=2, origin=(0,0), y=0)

        self.enemies = []
        self.game_over = False

        self.next_wave()

    def update(self):
        if self.game_over or self.paused:
            return
        self.ammo_text.text = f'{self.gun.ammo}/{self.gun.mag_size}'
        if len(self.enemies) == 0:
            self.next_wave()

    def input(self, key):
        if key == 'left mouse down':
            self.gun.shoot()
        if key == 'r':
            self.gun.reload()
        if key == 'right mouse down':
            camera.animate('fov', FOV_AIM, duration=.08)
        if key == 'right mouse up':
            camera.animate('fov', FOV_DEFAULT, duration=.08)
        if key == 'p':
            self.paused = not self.paused
            mouse.locked = not self.paused
            self.show_toast('Paused' if self.paused else 'Resumed')
        if key == 'escape':
            application.quit()
        if key == 'r' and self.game_over:
            self.restart()

    def next_wave(self):
        self.wave += 1
        count = max(1,int(ENEMY_COUNT_BASE * ENEMY_GROWTH**(self.wave-1)))
        self.enemies = [Enemy(position=(random.uniform(-WORLD_SIZE/2,WORLD_SIZE/2),1,random.uniform(-WORLD_SIZE/2,WORLD_SIZE/2))) for _ in range(count)]
        self.wave_text.text = f'Wave {self.wave}'
        self.show_toast(f'Wave {self.wave} — {count} enemies')

    def damage_player(self, amount):
        if self.paused or self.game_over:
            return
        self.player_hp = max(0, self.player_hp - amount)
        pct = self.player_hp / PLAYER_MAX_HP
        self.hp_bar.scale_x = .36 * pct
        if self.player_hp <= 0:
            self.game_over_screen()

    def game_over_screen(self):
        self.game_over = True
        self.lose_text.text = "YOU LOST"

    def show_toast(self, msg):
        self.toast.text = msg
        self.toast.alpha = 1
        self.toast.animate('alpha', 0, duration=1.5)

    def restart(self):
        for e in list(self.enemies):
            destroy(e)
        self.enemies.clear()
        self.score = 0
        self.wave = 0
        self.player_hp = PLAYER_MAX_HP
        self.hp_bar.scale_x = .36
        self.score_text.text = 'Score 0'
        self.wave_text.text = 'Wave 0'
        self.lose_text.text = ''
        self.game_over = False
        camera.fov = FOV_DEFAULT
        self.next_wave()

# ---------------- Run Game ---------------- #
app = Ursina()
game = Game()
Sky()
app.run()

