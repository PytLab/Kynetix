'''
    Script to plot merged energy profile
'''
import sys

import matplotlib.pyplot as plt

from catplot.en_profile import *
from catplot.functions import verify_multi_shape, verify_attrlen
from merge_data import *  # get rxn_equations & energy_tuples

#check the shape of input data
verify_multi_shape(multi_rxn_equations, multi_energy_tuples)

nlines = len(multi_rxn_equations)  # number of lines

if 'init_y_offsets' in dir():
    verify_attrlen(init_y_offsets, nlines)
else:
    init_y_offsets = [0.0]*nlines

points_list = []
print "Plotting single multi-energy profile..."
#zip data
zipped_data = zip(multi_rxn_equations, multi_energy_tuples, init_y_offsets)
for idx, (rxn_equations, energy_tuples, init_y_offset) in enumerate(zipped_data):
    fname = 'multi_energy_diagram_' + str(idx).zfill(2)
    print "Plotting diagram " + fname + "..."
    fig, x_total, y_total = \
        plot_multi_energy_diagram(rxn_equations, energy_tuples,
                                  init_y_offset=init_y_offset,
                                  n=10000, show_mode='save',
                                  fname=fname)
    print "Ok."
    points_list.append((x_total, y_total))

#merge lines
print 'Merge diagrams...'
new_fig = plt.figure(figsize=(16, 9))
# transparent figure
if len(sys.argv) > 2 and sys.argv[2] == '--trans':
    new_fig.patch.set_alpha(0)

ax = new_fig.add_subplot(111)
# transparent axe
if len(sys.argv) > 2 and sys.argv[2] == '--trans':
    ax.patch.set_alpha(0)

#remove xticks
ax.set_xticks([])
ax.set_xmargin(0.03)

#set attributes of y-axis
ax.set_ymargin(0.03)
if 'ylim' in dir():
    ymin, ymax = ylim
    ax.set_ylim(ymin, ymax)
    if 'n_yticks' in dir():  # must set ylim befor setting n_yticks
        ax.set_yticks(np.linspace(ymin, ymax, n_yticks))
if 'yticklabels' in dir():
    ax.set_yticklabels(yticklabels)

#colors setting
if 'colors' in dir():
    verify_attrlen(colors, nlines)
elif nlines <= 6:
    colors = ['#A52A2A', '#000000', '#36648B', '#FF7256', '#008B8B', '#7A378B']
else:
    raise ValueError('Line color is undefined.')

#shadow attrs setting
shadow_depth = shadow_depth if 'shadow_depth' in dir() else 7
shadow_color = shadow_color if 'shadow_color' in dir() else '#595959'
offset_coeff = offset_coeff if 'offset_coeff' in dir() else 9.0

#line attr setting
line_width = line_width if 'line_width' in dir() else 4.5

for color, points in zip(colors, points_list):
    add_line_shadow(ax, *points, depth=shadow_depth, color=shadow_color,
                    line_width=3, offset_coeff=offset_coeff)
    ax.plot(*points, linewidth=line_width, color=color)

if sys.argv[1] == '--show':
    new_fig.show()
elif sys.argv[1] == '--save':
    new_fig.savefig('./energy_profile/merged_energy_profile.png', dpi=500)
print 'Ok.'
