import pygame
import random
import math
import time
from collections import deque

pygame.init()

# ─── Screen / Layout ──────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1100, 720
PANEL_X  = 760
PANEL_W  = SCREEN_W - PANEL_X

ROAD_W   = 130          # wider road = more zoomed-in look
CX       = PANEL_X // 2
CY       = SCREEN_H // 2

# ─── Colours ──────────────────────────────────────────────────────────────────
ASPHALT_COLOR   = (52, 52, 58)
ROAD_COLOR      = (38, 38, 44)
BG_COLOR        = (45, 100, 45)
MARKING_COLOR   = (230, 200, 50)
STOP_LINE_COLOR = (255, 255, 255)
PANEL_BG        = (18, 18, 26)
PANEL_BORDER    = (60, 60, 85)

RED_LIGHT   = (220,  50,  50)
GREEN_LIGHT = ( 50, 210,  80)
DARK_LIGHT  = ( 50,  50,  50)

CAR_COLOR    = ( 70, 130, 200)
EMRG_COLOR   = (210,  45,  45)
CAR_OUTLINE  = ( 25,  70, 140)
EMRG_OUTLINE = (140,  20,  20)

VEHICLE_LEN  = 32
VEHICLE_WID  = 20
VEHICLE_GAP  = 8
STOP_OFFSET  = 10

FPS            = 60
AI_INTERVAL    = 2.0
FIRST_AI_DELAY = 5.0

# ─── Heuristic ────────────────────────────────────────────────────────────────
def heuristic_score(lane):
    vc   = lane.vehicle_count
    wt   = lane.avg_waiting_time()
    ar   = lane.arrival_rate
    emrg = 1 if lane.emergency_present else 0
    return 0.4*vc + 0.3*wt + 0.2*ar + 10*emrg

# ─── Vehicle ──────────────────────────────────────────────────────────────────
class Vehicle:
    def __init__(self, direction, is_emergency=False):
        self.direction    = direction
        self.is_emergency = is_emergency
        self.speed        = 2.2
        self.waiting      = False
        self.wait_start   = None
        self.total_wait   = 0.0
        self.passed       = False
        self.crossed      = False   # True once the vehicle passes its stop line
        self.flash_timer  = 0
        self.flash_on     = False

        hw  = ROAD_W // 2
        hl  = VEHICLE_LEN // 2
        pad = 20

        if direction == 'N':
            self.x      = CX + hw // 2
            self.y      = SCREEN_H + hl + pad
            self.stop_y = CY + hw + STOP_OFFSET + hl
        elif direction == 'S':
            self.x      = CX - hw // 2
            self.y      = -(hl + pad)
            self.stop_y = CY - hw - STOP_OFFSET - hl
        elif direction == 'E':
            self.x      = -(hl + pad)
            self.y      = CY - hw // 2
            self.stop_x = CX - hw - STOP_OFFSET - hl
        elif direction == 'W':
            self.x      = PANEL_X + hl + pad
            self.y      = CY + hw // 2
            self.stop_x = CX + hw + STOP_OFFSET + hl

        self.color   = EMRG_COLOR   if is_emergency else CAR_COLOR
        self.outline = EMRG_OUTLINE if is_emergency else CAR_OUTLINE

    def queue_stop(self, slot):
        step = VEHICLE_LEN + VEHICLE_GAP
        if self.direction == 'N':
            return self.stop_y + slot * step
        elif self.direction == 'S':
            return self.stop_y - slot * step
        elif self.direction == 'E':
            return self.stop_x + slot * step
        elif self.direction == 'W':
            return self.stop_x - slot * step

    def update(self, green, slot):
        if self.is_emergency:
            self.flash_timer += 1
            if self.flash_timer >= 12:
                self.flash_timer = 0
                self.flash_on = not self.flash_on

        # Once crossed the stop line, just drive freely until off-screen
        if self.crossed:
            if self.direction == 'N':
                self.y -= self.speed
                if self.y < -60:
                    self.passed = True
            elif self.direction == 'S':
                self.y += self.speed
                if self.y > SCREEN_H + 60:
                    self.passed = True
            elif self.direction == 'E':
                self.x += self.speed
                if self.x > PANEL_X + 60:
                    self.passed = True
            elif self.direction == 'W':
                self.x -= self.speed
                if self.x < -60:
                    self.passed = True
            return

        # Stop-line thresholds — crossing point is the stop line itself
        hw = ROAD_W // 2
        if self.direction == 'N':
            cross_threshold = CY + hw          # stop line y for N lane
        elif self.direction == 'S':
            cross_threshold = CY - hw          # stop line y for S lane
        elif self.direction == 'E':
            cross_threshold = CX - hw          # stop line x for E lane
        elif self.direction == 'W':
            cross_threshold = CX + hw          # stop line x for W lane

        target = self.queue_stop(slot)

        if self.direction == 'N':
            if not green:
                if self.y > target + 0.5:
                    self.y -= self.speed
                else:
                    self._start_wait()
            else:
                self._clear_wait()
                self.y -= self.speed
                if self.y <= cross_threshold:
                    self.crossed = True

        elif self.direction == 'S':
            if not green:
                if self.y < target - 0.5:
                    self.y += self.speed
                else:
                    self._start_wait()
            else:
                self._clear_wait()
                self.y += self.speed
                if self.y >= cross_threshold:
                    self.crossed = True

        elif self.direction == 'E':
            if not green:
                if self.x < target - 0.5:
                    self.x += self.speed
                else:
                    self._start_wait()
            else:
                self._clear_wait()
                self.x += self.speed
                if self.x >= cross_threshold:
                    self.crossed = True

        elif self.direction == 'W':
            if not green:
                if self.x > target + 0.5:
                    self.x -= self.speed
                else:
                    self._start_wait()
            else:
                self._clear_wait()
                self.x -= self.speed
                if self.x <= cross_threshold:
                    self.crossed = True

    def _start_wait(self):
        if not self.waiting:
            self.waiting    = True
            self.wait_start = time.time()

    def _clear_wait(self):
        if self.wait_start:
            self.total_wait += time.time() - self.wait_start
            self.wait_start  = None
        self.waiting = False

    def draw(self, surf):
        hw, hl = VEHICLE_WID / 2, VEHICLE_LEN / 2
        if self.direction in ('N', 'S'):
            rect = pygame.Rect(self.x - hw, self.y - hl, VEHICLE_WID, VEHICLE_LEN)
        else:
            rect = pygame.Rect(self.x - hl, self.y - hw, VEHICLE_LEN, VEHICLE_WID)

        col = (255, 210, 0) if (self.is_emergency and self.flash_on) else self.color
        pygame.draw.rect(surf, col,          rect, border_radius=4)
        pygame.draw.rect(surf, self.outline, rect, 2, border_radius=4)

        wc = (190, 225, 255) if not self.is_emergency else (255, 190, 190)
        if self.direction == 'N':
            pygame.draw.rect(surf, wc, (self.x-hw+3, self.y-hl+4,  VEHICLE_WID-6, 7), border_radius=2)
        elif self.direction == 'S':
            pygame.draw.rect(surf, wc, (self.x-hw+3, self.y+hl-11, VEHICLE_WID-6, 7), border_radius=2)
        elif self.direction == 'E':
            pygame.draw.rect(surf, wc, (self.x-hl+4, self.y-hw+3,  7, VEHICLE_WID-6), border_radius=2)
        elif self.direction == 'W':
            pygame.draw.rect(surf, wc, (self.x+hl-11,self.y-hw+3,  7, VEHICLE_WID-6), border_radius=2)

        if self.is_emergency:
            f = pygame.font.SysFont('Arial', 9, bold=True)
            lbl = f.render('EMG', True, (255, 255, 255))
            surf.blit(lbl, (rect.centerx - lbl.get_width()//2,
                            rect.centery - lbl.get_height()//2))

# ─── Lane ─────────────────────────────────────────────────────────────────────
class Lane:
    def __init__(self, direction):
        self.direction         = direction
        self.vehicles          = []
        self.green             = False
        self.arrival_log       = deque()
        self.arrival_rate      = 0
        self.emergency_present = False

    @property
    def vehicle_count(self):
        # Only vehicles that haven't crossed the stop line count toward heuristic
        return sum(1 for v in self.vehicles if not v.crossed)

    def avg_waiting_time(self):
        now   = time.time()
        waits = []
        for v in self.vehicles:
            if v.crossed:
                continue   # already past the signal, ignore
            if v.waiting and v.wait_start:
                waits.append(now - v.wait_start + v.total_wait)
            else:
                waits.append(v.total_wait)
        return sum(waits) / len(waits) if waits else 0.0

    def add_vehicle(self, is_emergency=False):
        v = Vehicle(self.direction, is_emergency)
        self.vehicles.append(v)
        self.arrival_log.append(time.time())

    def update(self):
        now = time.time()
        while self.arrival_log and now - self.arrival_log[0] > 60:
            self.arrival_log.popleft()
        self.arrival_rate      = len(self.arrival_log)
        self.emergency_present = any(v.is_emergency for v in self.vehicles if not v.crossed)
        self.vehicles          = [v for v in self.vehicles if not v.passed]

        # Queue slots only for vehicles still waiting before the stop line
        slot = 0
        for v in self.vehicles:
            if not v.crossed:
                v.update(self.green, slot)
                slot += 1
            else:
                v.update(self.green, 0)  # slot arg unused once crossed

    def draw(self, surf):
        for v in self.vehicles:
            v.draw(surf)

# ─── TrafficSignal ────────────────────────────────────────────────────────────
# Signal placement strategy:
#   N signal → posted on the RIGHT kerb of the north road arm, facing southbound driver
#   S signal → posted on the LEFT kerb of the south road arm, facing northbound driver
#   E signal → posted on the BOTTOM kerb of the east road arm, facing westbound driver
#   W signal → posted on the TOP kerb of the west road arm, facing eastbound driver
#
#  Each signal box sits just outside the stop line, clearly beside its own road.
class TrafficSignal:
    BOX_W = 24
    BOX_H = 52

    def __init__(self, direction):
        self.direction = direction
        self.state     = 'red'
        hw = ROAD_W // 2
        bw, bh = self.BOX_W, self.BOX_H
        margin = 10   # gap between road edge and signal box

        if direction == 'N':
            # right-hand side of north arm, at the stop line (CY+hw)
            self.bx = CX + hw + margin
            self.by = CY + hw - bh       # top of box sits at stop line level
            self.pole_bottom = True
            self.label_anchor = 'top'

        elif direction == 'S':
            # left-hand side of south arm, at the stop line (CY-hw)
            self.bx = CX - hw - margin - bw
            self.by = CY - hw            # box starts at stop line level
            self.pole_bottom = False
            self.label_anchor = 'bottom'

        elif direction == 'E':
            # bottom side of east arm, at the stop line (CX-hw)
            self.bx = CX - hw - bw + 4
            self.by = CY + hw + margin
            self.pole_bottom = False
            self.label_anchor = 'top'

        elif direction == 'W':
            # top side of west arm, at the stop line (CX+hw)
            self.bx = CX + hw - bw - 4
            self.by = CY - hw - margin - bh
            self.pole_bottom = True
            self.label_anchor = 'bottom'

    def set_state(self, state):
        self.state = state

    def draw(self, surf):
        bx, by = self.bx, self.by
        bw, bh = self.BOX_W, self.BOX_H

        # pole
        px = bx + bw // 2
        if self.pole_bottom:
            pygame.draw.line(surf, (90, 90, 90), (px, by + bh), (px, by + bh + 22), 4)
        else:
            pygame.draw.line(surf, (90, 90, 90), (px, by), (px, by - 22), 4)

        # housing shadow
        pygame.draw.rect(surf, (12, 12, 12), (bx+2, by+2, bw, bh), border_radius=5)
        # housing body
        pygame.draw.rect(surf, (25, 25, 25), (bx, by, bw, bh), border_radius=5)
        pygame.draw.rect(surf, (95, 95, 95), (bx, by, bw, bh), 1, border_radius=5)

        cy_red   = by + 13
        cy_green = by + bh - 13

        red_c   = RED_LIGHT   if self.state == 'red'   else DARK_LIGHT
        green_c = GREEN_LIGHT if self.state == 'green' else DARK_LIGHT

        pygame.draw.circle(surf, red_c,   (bx + bw//2, cy_red),   9)
        pygame.draw.circle(surf, green_c, (bx + bw//2, cy_green), 9)

        # glow
        if self.state == 'green':
            g = pygame.Surface((36, 36), pygame.SRCALPHA)
            pygame.draw.circle(g, (50, 210, 80, 80), (18, 18), 18)
            surf.blit(g, (bx + bw//2 - 18, cy_green - 18))
        else:
            g = pygame.Surface((36, 36), pygame.SRCALPHA)
            pygame.draw.circle(g, (220, 50, 50, 80), (18, 18), 18)
            surf.blit(g, (bx + bw//2 - 18, cy_red - 18))

        # direction label
        font  = pygame.font.SysFont('Arial', 11, bold=True)
        names = {'N': 'NORTH', 'S': 'SOUTH', 'E': 'EAST', 'W': 'WEST'}
        lbl   = font.render(names[self.direction], True, (220, 220, 240))
        lw, lh = lbl.get_width(), lbl.get_height()
        lx = bx + bw//2 - lw//2

        if self.label_anchor == 'top':
            ly = by + bh + (26 if self.pole_bottom else 4)
        else:
            ly = by - (26 if not self.pole_bottom else 4) - lh

        # pill background
        pygame.draw.rect(surf, (28, 28, 46),
                         (lx - 3, ly - 1, lw + 6, lh + 2), border_radius=3)
        surf.blit(lbl, (lx, ly))

# ─── TrafficSimulation ────────────────────────────────────────────────────────
class TrafficSimulation:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("AI Traffic Signal Control System")
        self.clock  = pygame.time.Clock()

        self.lanes   = {d: Lane(d)          for d in ('N', 'S', 'E', 'W')}
        self.signals = {d: TrafficSignal(d) for d in ('N', 'S', 'E', 'W')}

        # All signals RED at start; AI not running yet
        self.current_green      = None
        self.ai_started         = False
        self.first_vehicle_time = None   # set when first button is pressed

        self.last_ai_time  = 0.0
        self.scores        = {d: 0.0 for d in ('N', 'S', 'E', 'W')}
        self.score_display = {d: 0.0 for d in ('N', 'S', 'E', 'W')}

        self.font_sm  = pygame.font.SysFont('Consolas', 13)
        self.font_md  = pygame.font.SysFont('Consolas', 15, bold=True)
        self.font_ttl = pygame.font.SysFont('Consolas', 20, bold=True)

        self._build_buttons()

    # ── Buttons ───────────────────────────────────────────────────────────────
    def _build_buttons(self):
        bw      = (PANEL_W - 28) // 2
        bh      = 27
        start_y = 444
        row_h   = 36
        bx_base = PANEL_X + 10
        dir_full = {'N': 'North', 'S': 'South', 'E': 'East', 'W': 'West'}

        entries = [('N', False), ('N', True),
                   ('S', False), ('S', True),
                   ('E', False), ('E', True),
                   ('W', False), ('W', True)]

        self.buttons = []
        for i, (d, emrg) in enumerate(entries):
            row  = i // 2
            col  = i %  2
            rect = pygame.Rect(bx_base + col*(bw+8), start_y + row*row_h, bw, bh)
            col_color = (148, 32, 32) if emrg else (32, 82, 152)
            label     = f"{dir_full[d]} {'EMRG' if emrg else 'Car'}"
            self.buttons.append({'rect': rect, 'dir': d, 'emrg': emrg,
                                  'label': label, 'color': col_color, 'hover': False})

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self):
        running = True
        while running:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_click(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    for btn in self.buttons:
                        btn['hover'] = btn['rect'].collidepoint(event.pos)

            self._ai_step()
            self._update()
            self._draw()
            pygame.display.flip()
        pygame.quit()

    # ── AI ────────────────────────────────────────────────────────────────────
    def _ai_step(self):
        now = time.time()

        if self.first_vehicle_time is None:
            return   # no vehicle added yet

        if not self.ai_started:
            if now - self.first_vehicle_time >= FIRST_AI_DELAY:
                self.ai_started   = True
                self.last_ai_time = now
            else:
                return   # still in observation window

        if now - self.last_ai_time < AI_INTERVAL:
            return
        self.last_ai_time = now

        for d, lane in self.lanes.items():
            if lane.vehicle_count > 0:
                self.scores[d] = heuristic_score(lane)
            else:
                self.scores[d] = 0.0

        active = {d: s for d, s in self.scores.items()
                  if self.lanes[d].vehicle_count > 0}
        if not active:
            self.current_green = None
            for d in ('N', 'S', 'E', 'W'):
                self.signals[d].set_state('red')
                self.lanes[d].green = False
            return

        best = max(active, key=active.get)
        self.current_green = best

        for d in ('N', 'S', 'E', 'W'):
            is_green = (d == best)
            self.signals[d].set_state('green' if is_green else 'red')
            self.lanes[d].green = is_green

    # ── Update ────────────────────────────────────────────────────────────────
    def _update(self):
        for lane in self.lanes.values():
            lane.update()
        for d in ('N', 'S', 'E', 'W'):
            self.score_display[d] += (self.scores[d] - self.score_display[d]) * 0.12

    # ── Click ─────────────────────────────────────────────────────────────────
    def _handle_click(self, pos):
        for btn in self.buttons:
            if btn['rect'].collidepoint(pos):
                self.lanes[btn['dir']].add_vehicle(btn['emrg'])
                if self.first_vehicle_time is None:
                    self.first_vehicle_time = time.time()

    # ── Draw ──────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(BG_COLOR)
        self._draw_world()
        for lane in self.lanes.values():
            lane.draw(self.screen)
        for sig in self.signals.values():
            sig.draw(self.screen)
        self._draw_panel()

    def _draw_world(self):
        surf = self.screen
        hw   = ROAD_W // 2

        # Road arms
        pygame.draw.rect(surf, ASPHALT_COLOR, (CX-hw, 0,       ROAD_W,  SCREEN_H))
        pygame.draw.rect(surf, ASPHALT_COLOR, (0,     CY-hw,   PANEL_X, ROAD_W))
        # Intersection
        pygame.draw.rect(surf, ROAD_COLOR,    (CX-hw, CY-hw,   ROAD_W,  ROAD_W))

        # Kerb edges
        kerb, kw = (105, 105, 110), 2
        pygame.draw.line(surf, kerb, (CX-hw, 0),        (CX-hw, CY-hw),    kw)
        pygame.draw.line(surf, kerb, (CX-hw, CY+hw),    (CX-hw, SCREEN_H), kw)
        pygame.draw.line(surf, kerb, (CX+hw, 0),        (CX+hw, CY-hw),    kw)
        pygame.draw.line(surf, kerb, (CX+hw, CY+hw),    (CX+hw, SCREEN_H), kw)
        pygame.draw.line(surf, kerb, (0,     CY-hw),    (CX-hw, CY-hw),    kw)
        pygame.draw.line(surf, kerb, (CX+hw, CY-hw),    (PANEL_X, CY-hw),  kw)
        pygame.draw.line(surf, kerb, (0,     CY+hw),    (CX-hw, CY+hw),    kw)
        pygame.draw.line(surf, kerb, (CX+hw, CY+hw),    (PANEL_X, CY+hw),  kw)

        # Dashed centre lines
        dash, gap = 24, 16
        y = 0
        while y < SCREEN_H:
            if not (CY - hw <= y <= CY + hw):
                pygame.draw.rect(surf, MARKING_COLOR, (CX-1, y, 2, dash))
            y += dash + gap
        x = 0
        while x < PANEL_X:
            if not (CX - hw <= x <= CX + hw):
                pygame.draw.rect(surf, MARKING_COLOR, (x, CY-1, dash, 2))
            x += dash + gap

        # Stop lines
        sw = 4
        pygame.draw.line(surf, STOP_LINE_COLOR, (CX-hw, CY+hw),  (CX+hw, CY+hw),  sw)
        pygame.draw.line(surf, STOP_LINE_COLOR, (CX-hw, CY-hw),  (CX+hw, CY-hw),  sw)
        pygame.draw.line(surf, STOP_LINE_COLOR, (CX-hw, CY-hw),  (CX-hw, CY+hw),  sw)
        pygame.draw.line(surf, STOP_LINE_COLOR, (CX+hw, CY-hw),  (CX+hw, CY+hw),  sw)

        # Road direction labels painted on asphalt
        lf = pygame.font.SysFont('Arial', 13, bold=True)
        lc = (120, 110, 60)
        for txt, tx, ty in [
            ('NORTH', CX+hw+14, CY+hw+50),
            ('SOUTH', CX-hw-58, CY-hw-64),
            ('EAST',  CX-hw-56, CY+hw+18),
            ('WEST',  CX+hw+14, CY-hw-28),
        ]:
            surf.blit(lf.render(txt, True, lc), (tx, ty))

        # Panel
        pygame.draw.rect(surf, PANEL_BG,     (PANEL_X, 0, PANEL_W, SCREEN_H))
        pygame.draw.line(surf, PANEL_BORDER, (PANEL_X, 0), (PANEL_X, SCREEN_H), 2)

    # ── Panel ─────────────────────────────────────────────────────────────────
    def _draw_panel(self):
        surf = self.screen
        px   = PANEL_X + 10
        pw   = PANEL_W - 20
        now  = time.time()
        dir_full = {'N': 'North', 'S': 'South', 'E': 'East', 'W': 'West'}

        # Title
        title = self.font_ttl.render("AI Traffic Control", True, (180, 200, 255))
        surf.blit(title, (PANEL_X + (PANEL_W - title.get_width())//2, 10))
        sub = self.font_sm.render("Heuristic Signal System", True, (110, 120, 155))
        surf.blit(sub, (PANEL_X + (PANEL_W - sub.get_width())//2, 32))
        pygame.draw.line(surf, PANEL_BORDER, (PANEL_X+6, 52), (SCREEN_W-6, 52), 1)

        # ── Status box ──
        if self.first_vehicle_time is None:
            pygame.draw.rect(surf, (38, 38, 58), (px, 58, pw, 36), border_radius=6)
            pygame.draw.rect(surf, (80, 80, 110),(px, 58, pw, 36), 1, border_radius=6)
            msg = self.font_md.render("Add vehicles to begin...", True, (150, 150, 195))
            surf.blit(msg, (PANEL_X + (PANEL_W - msg.get_width())//2, 67))

        elif not self.ai_started:
            remaining = max(0.0, FIRST_AI_DELAY - (now - self.first_vehicle_time))
            pygame.draw.rect(surf, (58, 48, 18), (px, 58, pw, 36), border_radius=6)
            pygame.draw.rect(surf, (200,160, 40),(px, 58, pw, 36), 1, border_radius=6)
            msg = self.font_md.render(f"AI starts in  {remaining:.1f}s", True, (240, 200, 80))
            surf.blit(msg, (PANEL_X + (PANEL_W - msg.get_width())//2, 67))

        else:
            gd    = self.current_green
            label = f"GREEN: {dir_full[gd]} Lane" if gd else "Evaluating..."
            pygame.draw.rect(surf, (22, 68, 22), (px, 58, pw, 36), border_radius=6)
            pygame.draw.rect(surf, (50, 200, 70),(px, 58, pw, 36), 1, border_radius=6)
            gl = self.font_md.render(label, True, (80, 255, 120))
            surf.blit(gl, (PANEL_X + (PANEL_W - gl.get_width())//2, 67))

        # ── Table ──
        ty      = 104
        headers = ["Lane", "Vehs", "Wait", "Rate", "EMRG", "Score"]
        col_x   = [px, px+46, px+82, px+118, px+158, px+198]

        pygame.draw.rect(surf, (32, 32, 54), (px, ty, pw, 22))
        for i, h in enumerate(headers):
            surf.blit(self.font_sm.render(h, True, (148,150,200)), (col_x[i], ty+4))

        ty += 24
        row_bg = [(28, 28, 46), (34, 34, 54)]
        for ri, d in enumerate(('N', 'S', 'E', 'W')):
            lane  = self.lanes[d]
            score = self.score_display[d]
            ry    = ty + ri * 28

            if d == self.current_green and self.ai_started:
                pygame.draw.rect(surf, (20, 56, 20), (px, ry, pw, 26), border_radius=3)
                pygame.draw.rect(surf, (40,155, 40), (px, ry, pw, 26), 1, border_radius=3)
            else:
                pygame.draw.rect(surf, row_bg[ri%2], (px, ry, pw, 26), border_radius=3)

            tc     = (100, 255, 130) if (d == self.current_green and self.ai_started) \
                     else (200, 200, 220)
            emrg_c = (255, 80, 80) if lane.emergency_present else tc

            vals   = [dir_full[d], str(lane.vehicle_count),
                      f"{lane.avg_waiting_time():.1f}s", str(lane.arrival_rate),
                      "YES" if lane.emergency_present else "NO", f"{score:.1f}"]
            colors = [tc, tc, tc, tc, emrg_c, tc]
            for i, (v, vc) in enumerate(zip(vals, colors)):
                surf.blit(self.font_sm.render(v, True, vc), (col_x[i], ry+6))

        ty += 4*28 + 8

        # ── Score bars ──
        pygame.draw.line(surf, PANEL_BORDER, (PANEL_X+6, ty), (SCREEN_W-6, ty), 1)
        ty += 6
        sb = self.font_md.render("Priority Scores", True, (150, 150, 210))
        surf.blit(sb, (PANEL_X + (PANEL_W - sb.get_width())//2, ty))
        ty += 20

        bar_cols   = {'N':(70,130,200),'S':(70,170,130),'E':(200,150,50),'W':(170,80,200)}
        max_score  = max(self.score_display.values()) or 1
        for d in ('N', 'S', 'E', 'W'):
            sc    = self.score_display[d]
            bar_w = int((sc / max_score) * (pw - 52)) if sc > 0 else 0
            surf.blit(self.font_sm.render(dir_full[d][0], True, (200,200,220)), (px, ty+1))
            bc = (50, 210, 80) if (d == self.current_green and self.ai_started) \
                 else bar_cols[d]
            pygame.draw.rect(surf, (38,38,58), (px+16, ty, pw-52, 15), border_radius=3)
            if bar_w > 0:
                pygame.draw.rect(surf, bc, (px+16, ty, bar_w, 15), border_radius=3)
            score_txt = f"{sc:.1f}" if sc > 0 else "0.0"
            surf.blit(self.font_sm.render(score_txt, True, (170,170,180)),
                      (px + pw - 36, ty))
            ty += 20

        # ── Formula ──
        pygame.draw.line(surf, PANEL_BORDER, (PANEL_X+6, ty+2), (SCREEN_W-6, ty+2), 1)
        ty += 10
        for line in ("Heuristic Formula:",
                     "0.4·vehicles + 0.3·wait",
                     "+ 0.2·arrRate + 10·emrg"):
            surf.blit(self.font_sm.render(line, True, (105,115,150)), (px, ty))
            ty += 15

        # ── Buttons ──
        pygame.draw.line(surf, PANEL_BORDER, (PANEL_X+6, 436), (SCREEN_W-6, 436), 1)
        bl = self.font_md.render("Add Vehicles", True, (150, 150, 210))
        surf.blit(bl, (PANEL_X + (PANEL_W - bl.get_width())//2, 438))

        for btn in self.buttons:
            col = tuple(min(255, c+38) for c in btn['color']) if btn['hover'] else btn['color']
            pygame.draw.rect(surf, col,            btn['rect'], border_radius=5)
            pygame.draw.rect(surf, (168, 168, 168),btn['rect'], 1, border_radius=5)
            bt = self.font_sm.render(btn['label'], True, (230, 230, 230))
            surf.blit(bt, (btn['rect'].centerx - bt.get_width()//2,
                           btn['rect'].centery - bt.get_height()//2))

        # Footer
        ft = self.font_sm.render("ESC to quit", True, (72, 72, 98))
        surf.blit(ft, (PANEL_X + (PANEL_W - ft.get_width())//2, SCREEN_H - 18))

# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    sim = TrafficSimulation()
    sim.run()