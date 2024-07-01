import pickle
from matplotlib import pyplot as plt
from matplotlib.widgets import Button
from matplotlib.text import Annotation


with open('quality_results_first_6_pulses.pkl', 'rb') as f:
	results = pickle.load(f)

drop_rate = []
ber = []
labels = []

for result in results:
	drop_rate.append(result[3])
	ber.append(result[5]/8.)
	#annotation string:
	labels.append(str(result))

# plt.figure()
# plt.scatter(ber, drop_rate)

# plt.show()

# draw a scatter-plot of the generated values
fig = plt.figure(figsize=(20, 16))
ax = plt.subplot()
# plt.xlabel("Bit error rate")
# plt.ylabel("Dropped packet rate")
# plt.yscale('log')
# plt.xscale('log')

# extract the scatterplot drawing in a separate function so we ca re-use the code
def draw_scatterplot():
	ax.scatter(
		ber,
		drop_rate,
		picker=True
	)
	plt.xlabel("Bit error rate")
	plt.ylabel("Dropped packet rate")
	plt.yscale('log')
	plt.xscale('log')


# draw the initial scatterplot
draw_scatterplot()

# create and add an annotation object (a text label)
def annotate(axis, text, x, y):
    text_annotation = Annotation(text, xy=(x, y), xycoords='data')
    axis.add_artist(text_annotation)

# define the behaviour -> what happens when you pick a dot on the scatterplot by clicking close to it
def onpick(event):
    # step 1: take the index of the dot which was picked
    ind = event.ind

    # step 2: save the actual coordinates of the click, so we can position the text label properly
    label_pos_x = event.mouseevent.xdata
    label_pos_y = event.mouseevent.ydata

    # just in case two dots are very close, this offset will help the labels not appear one on top of each other
    offset = 0

    # if the dots are to close one to another, a list of dots clicked is returned by the matplotlib library
    for i in ind:
        # step 3: take the label for the corresponding instance of the data
        label = labels[i]

        # step 4: log it for debugging purposes
        # print "index", i, label

        # step 5: create and add the text annotation to the scatterplot
        annotate(
            ax,
            label,
            label_pos_x + offset,
            label_pos_y + offset
        )

        # step 6: force re-draw
        ax.figure.canvas.draw_idle()

        # alter the offset just in case there are more than one dots affected by the click
        offset += 0.01


# connect the click handler function to the scatterplot
fig.canvas.mpl_connect('pick_event', onpick)

# create the "clear all" button, and place it somewhere on the screen
ax_clear_all = plt.axes([0.0, 0.0, 0.1, 0.05])
button_clear_all = Button(ax_clear_all, 'Clear all')


# define the "clear all" behaviour
def onclick(event):
    # step 1: we clear all artist object of the scatter plot
    ax.cla()

    # step 2: we re-populate the scatterplot only with the dots not the labels
    draw_scatterplot()

    # step 3: we force re-draw
    ax.figure.canvas.draw_idle()


# link the event handler function to the click event on the button
button_clear_all.on_clicked(onclick)

# initial drawing of the scatterplot
plt.plot()
# print "scatterplot done"

# present the scatterplot
plt.show()