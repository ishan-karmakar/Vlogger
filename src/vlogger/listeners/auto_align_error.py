from vlogger.listeners import Listener
import re
import logging, math
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import seaborn as sns
import pandas as pd
from matplotlib.widgets import Button
logger = logging.getLogger(__name__)

class AutoAlignError(Listener):
    # auto_align_start - Boolean field that represents when auto align starts
    # target_angle - Integer/float field that represents the target angle for rotation controller
    # target_y - Integer/float field that represents the target y controller goal
    # current_angle - Integer/float field that represents the current angle for rotation controller
    # current_y - Integer/float field that represents the current y controller goal
    # current_scoring_state - Integer/float field that represents the scoring state of the scorer
    # game_piece - Integer/float field that represents the game piece of the scorer
    def __init__(self, auto_align_start, target_angle, target_y, current_angle, current_y, current_scoring_state, game_piece):
        super(AutoAlignError, self).__init__(
            aa_start_regex = auto_align_start,
            target_angle_regex = target_angle,
            target_y_regex = target_y,
            current_angle_regex = current_angle,
            current_y_regex = current_y,
            current_ss_regex = current_scoring_state,
            game_piece_regex = game_piece
        )

        self.target_angle = 0
        self.target_y = 0
        self.cur_state = {
            "timestamps": [],
            "rot_errors": [],
            "y_errors": [],
        }
        self.auto_aligns = []
        self.cur_df = 0
        self.reset_state()

    def __call__(self, name: str, timestamp: int, data):
        if self.aa_start_regex.match(name):
            if data:
                self.start_alignment = timestamp
            else:
                # Auto alignment was aborted because rotation align was set to false
                self.reset_state()
        elif self.target_angle_regex.match(name):
            self.target_angle = data
        elif self.target_y_regex.match(name):
            self.target_y = data
        elif self.current_angle_regex.match(name):
            self.current_angle = data.rotation.value
        elif self.current_y_regex.match(name):
            self.current_y = data
        elif self.current_ss_regex.match(name):
            self.scoring = data == 2
        elif self.game_piece_regex.match(name):
            self.coral = data == 0
        
        if self.start_alignment and self.coral:
            self.cur_state["timestamps"].append(timestamp / 1_000_000)
            self.cur_state["rot_errors"].append(abs(((self.target_angle - self.current_angle) * 180 / math.pi + 180) % 360 - 180))
            self.cur_state["y_errors"].append(abs(self.target_y - self.current_y) * 1_000)

            if self.scoring:
                self.auto_aligns.append(pd.DataFrame.from_dict(self.cur_state))
                self.reset_state()

    def reset_state(self):
        self.start_alignment = None
        self.current_angle = 0
        self.current_y = 0
        self.scoring = False
        self.cur_state["timestamps"].clear()
        self.cur_state["rot_errors"].clear()
        self.cur_state["y_errors"].clear()
    
    def eof(self):
        # Window will be able to fit 2 x 2 plots
        if not len(self.auto_aligns):
            return
        df = self.auto_aligns[self.cur_df]
        fig = plt.figure(layout="constrained")
        fig.supxlabel("Time")
        gs = GridSpec(2, 2, figure=fig)
        rot_ax = plt.subplot(gs[0, 0])
        y_ax = plt.subplot(gs[0, 1], sharex=rot_ax)

        sns.lineplot(df, x="timestamps", y="rot_errors", ax=rot_ax)
        sns.lineplot(df, x="timestamps", y="y_errors", ax=y_ax)

        rot_ax.set_ylim(0, max(3, df["rot_errors"].max()))
        rot_ax.set_ylabel("Rotation Error (deg)")
        rot_ax.set_title("Rotation Error over Time")
        rot_ax.axhline(1, ls="--", color="red", linewidth=0.75)

        y_ax.set_ylabel("Translation Error (mm)")
        y_ax.set_title("Translation Error over Time")
        y_ax.axhline(40, ls="--", color="red", linewidth=0.75)

        def next_plot(event):
            self.cur_df += 1
            if self.cur_df >= len(self.auto_aligns):
                self.cur_df = 0
            df = self.auto_aligns[self.cur_df]
            rot_ax.clear()
            y_ax.clear()
            sns.lineplot(df, x="timestamps", y="rot_errors", ax=rot_ax)
            sns.lineplot(df, x="timestamps", y="y_errors", ax=y_ax)
            rot_ax.axhline(1, ls="--", color="red", linewidth=0.75)
            y_ax.axhline(40, ls="--", color="red", linewidth=0.75)
            plt.draw()

        def prev_plot(event):
            self.cur_df -= 1
            if self.cur_df < 0:
                self.cur_df = len(self.auto_aligns) - 1
            df = self.auto_aligns[self.cur_df]
            rot_ax.clear()
            y_ax.clear()
            sns.lineplot(df, x="timestamps", y="rot_errors", ax=rot_ax)
            sns.lineplot(df, x="timestamps", y="y_errors", ax=y_ax)
            rot_ax.axhline(1, ls="--", color="red", linewidth=0.75)
            y_ax.axhline(40, ls="--", color="red", linewidth=0.75)
            plt.draw()

        axprev = fig.add_axes([0.73, 0.05, 0.1, 0.075])
        axnext = fig.add_axes([0.85, 0.05, 0.1, 0.075])
        bprev = Button(axprev, "Prev")
        bnext = Button(axnext, "Next")
        bprev.on_clicked(prev_plot)
        bnext.on_clicked(next_plot)

        plt.show()