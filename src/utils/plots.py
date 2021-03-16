import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from src.detection.yolov3.utils import draw_centroid
from mpl_toolkits.mplot3d.art3d import Path3DCollection, Poly3DCollection
from src.acceptance.base import best_fitting_hyperplane, rds_errors
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from typing import Tuple
import numpy as np
import matplotlib.colors as colors
import matplotlib.ticker as tick
from src.utils.camera import Camera

depth_image_cmap = 'gist_yarg'


def plot_depth_image(image):
    fig, ax = plt.subplots(1)
    _plot_depth_image(ax, image)
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    fig.tight_layout()
    plt.show()


class FixZorderCollection(Poly3DCollection):
    _zorder = -1

    @property
    def zorder(self):
        return self._zorder

    @zorder.setter
    def zorder(self, value):
        pass


def plot_two_hands_diff(hand1: Tuple[np.ndarray, np.ndarray, np.ndarray],
                        hand2: Tuple[np.ndarray, np.ndarray, np.ndarray],
                        cam: Camera,
                        show_norm=False, show_joint_errors=False):
    """
    Plots an image with a skeleton of the first hand and
    shows major differences from the second hand.

    Parameters
    ----------
    hand1 A tuple of three ndarrays: image, bbox, joints
    hand2 A tuple of three ndarrays: image, bbox, joints
    show_norm   bool True if vectors of the hand orientations should be displayed.
    show_diffs  bool True if differences between the hand poses should be displayed.
    """
    # plot the first skeleton
    # plot the second skeleton
    # compute the error between these skeletons
    # aggregate the errors for each joint
    # display the error for each joint
    image1, bbox1, joints1 = hand1
    image2, bbox2, joints2 = hand2

    if show_joint_errors:
        errors = rds_errors(np.expand_dims(joints1, axis=0), np.expand_dims(joints2, axis=0))[0, 0, :]
    else:
        errors = None

    fig, ax = plt.subplots()
    _plot_depth_image(ax, image1)
    joints1_2d = cam.world_to_pixel(joints1)
    # The image is cropped. Amend the joint coordinates to match the depth image
    joints1_2d = joints1_2d[..., :2] - bbox1[..., :2]
    _plot_skeleton_with_errors_2d(fig, ax, joints1_2d, joint_errors=errors, color='blue')
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.set_axis_off()
    fig.tight_layout()
    plt.show()


def cmap_subset(cmap, min, max):
    """ Create a subset of a cmap. """
    return colors.LinearSegmentedColormap.from_list(
        'trunc({n},{a:.2f},{b:.2f})'.format(n=cmap.name, a=min, b=max),
        cmap(np.linspace(min, max, 256)))


def _plot_skeleton_with_errors_2d(fig, ax, joints, joint_errors, color='r'):
    _plot_hand_skeleton_2d(ax, joints, wrist_index=0, scatter=False)

    min_err, max_err = joint_errors.min(), joint_errors.max()
    min_s, max_s = min_err * 4, max_err * 4  # 20., 200.
    scaled_errors = joint_errors / (max_err / (max_s - min_s)) + min_s

    cmap = cmap_subset(cm.get_cmap('Reds'), 0.4, 1.0)
    ax.scatter(joints[..., 0], joints[..., 1],
               c=joint_errors, cmap=cmap, s=scaled_errors, alpha=1, zorder=100)
    ax_inset = inset_axes(ax, width="100%", height="100%", loc='upper center',
                          bbox_to_anchor=(1.05, 0.71, 0.04, 0.24), bbox_transform=ax.transAxes)
    cbar = fig.colorbar(cm.ScalarMappable(cmap=cmap), cax=ax_inset, format='%.2f')
    colorbar_tick_labels = np.linspace(min_err, max_err, 5, dtype=float)
    cbar.set_ticks(np.linspace(0, 1, 5))
    cbar.set_ticklabels(colorbar_tick_labels)


def _plot_hand_skeleton_2d(ax, joints, wrist_index=0, s=20, alpha=1, marker='o', scatter=True):
    joints = np.squeeze(joints)  # get rid of surplus dimensions
    if joints.ndim != 2:
        raise ValueError(F"joints.ndim should be 2, but is {joints.ndim}")
    fingers_bases = np.arange(wrist_index + 1, wrist_index + 20, 4)
    wrist_joint = joints[wrist_index]
    finger_colors = ['r', 'm', 'c', 'g', 'b']
    if scatter:
        ax.scatter(wrist_joint[..., 0], wrist_joint[..., 1], c=finger_colors[-1], marker=marker, s=s, alpha=alpha)
    for i, finger_base in enumerate(fingers_bases):
        finger_joints = joints[finger_base:finger_base + 4]
        if scatter:
            ax.scatter(finger_joints[..., 0], finger_joints[..., 1], c=finger_colors[i], marker=marker, s=s,
                       alpha=alpha)
        xs = np.concatenate([wrist_joint[0:1], finger_joints[:, 0]])
        ys = np.concatenate([wrist_joint[1:2], finger_joints[:, 1]])
        # if joints.shape[-1] == 3:
        #     zs = np.concatenate([wrist_joint[2:3], finger_joints[:, 2]])
        #     ax.plot(xs, ys, zs=zs, c=finger_colors[i])
        # else:
        ax.plot(xs, ys, c=finger_colors[i])


def plot_joints(image, bbox, joints, show_norm=False):
    left, top, right, bottom = bbox
    width = right - left
    height = bottom - top

    fig = plt.figure(1)
    ax = fig.add_subplot(111, projection='3d')
    y = np.linspace(top, bottom, height)
    x = np.linspace(left, right, width)
    xx, yy = np.meshgrid(x, y)

    image3d = np.stack([xx, yy, image], axis=2)
    image3d[..., 2] = np.where(image3d[..., 2] == 0, np.max(image), image3d[..., 2])

    for i in range(len(ax.collections)):
        ax.collections[i].__class__ = FixZorderCollection
    _plot_skeleton_with_errors_2d(fig, ax, joints)

    if show_norm:
        # 0: wrist,
        # 1-4: index_mcp, index_pip, index_dip, index_tip,
        # 5-8: middle_mcp, middle_pip, middle_dip, middle_tip,
        # 9-12: ring_mcp, ring_pip, ring_dip, ring_tip,
        # 13-16: little_mcp, little_pip, little_dip, little_tip,
        # 17-20: thumb_mcp, thumb_pip, thumb_dip, thumb_tip

        palm_joints = np.take(joints, [0, 1, 5, 9, 13], axis=0)
        norm, mean = best_fitting_hyperplane(palm_joints)

        ax.quiver(mean[0], mean[1], mean[2], norm[0], norm[1], norm[2],
                  pivot='tail', length=np.std(joints), arrow_length_ratio=0.1)

    ax.view_init(azim=-90.0, elev=-90.0)  # aligns the 3d coord with the camera view
    fig.tight_layout()
    plt.show()


def plot_joints_only(joints):
    fig = plt.figure(1)
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter(joints[..., 0], joints[..., 1], joints[..., 2], marker='o', s=20, c="red", alpha=1)

    # ax.view_init(azim=0.0, elev=0.0)
    # ax.dist = 0

    # ax.xaxis.set_visible(False)
    # ax.yaxis.set_visible(False)

    ax.set_xlim([0, 360])
    ax.set_ylim([0, 360])
    fig.tight_layout()
    plt.show()


def _plot_depth_image(ax, image):
    ax.imshow(image, cmap=depth_image_cmap)


def plot_joints_2d(image, joints2d):
    fig, ax = plt.subplots(1)
    _plot_depth_image(ax, image)
    _plot_hand_skeleton_2d(ax, joints2d)
    ax.set_axis_off()
    fig.tight_layout()
    plt.show()


def plot_joints_2d_from_3d(image, joints3d, cam: Camera, show_norm=False):
    fig, ax = plt.subplots(1)
    _plot_depth_image(ax, image)
    # project joint coords through pinhole camera
    joints2d = cam.world_to_pixel(joints3d)
    _plot_hand_skeleton_2d(ax, joints2d)
    if show_norm:
        # 0: wrist,
        # 1-4: index_mcp, index_pip, index_dip, index_tip,
        # 5-8: middle_mcp, middle_pip, middle_dip, middle_tip,
        # 9-12: ring_mcp, ring_pip, ring_dip, ring_tip,
        # 13-16: little_mcp, little_pip, little_dip, little_tip,
        # 17-20: thumb_mcp, thumb_pip, thumb_dip, thumb_tip
        palm_joints = np.take(joints3d, [0, 1, 5, 9, 13], axis=0)
        norm, mean = best_fitting_hyperplane(palm_joints)
        norm_2d, mean_2d = cam.world_to_pixel(np.stack([mean + norm, mean]))
        ax.quiver(mean_2d[0], mean_2d[1], norm_2d[0], norm_2d[1], pivot='tail')
    fig.tight_layout()
    plt.show()


def plot_proportion_below_threshold(proportions, show_figure=True, fig_location=None):
    if np.max(proportions) <= 1:
        proportions *= 100
    fig, ax = plt.subplots(1, 1)
    ax.plot(proportions)
    ax.set_ylim(0, 100)
    ax.set_ylabel('Proportion of frames within distnace (%)')
    ax.set_xlabel('Max joint error threshold (mm)')
    fig.tight_layout()
    save_show_fig(fig, fig_location, show_figure)


def save_show_fig(fig, fig_location, show_figure):
    if fig_location:
        fig.savefig(fig_location)
    if show_figure:
        fig.show()
