# sankey.py
# 10 June 2026

# import modules
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.interpolate import make_interp_spline

# import Colours class
from utils import Colours

# Sankey class
class Sankey:
    """Class for creating a sankey diagram."""
    # constant values
    x_margin = 0.1
    y_margin = 0.2
    width = 0.5
    N = 100

    def __init__(self, nodes, links):
        """Creates an instance of the Sankey class."""
        # store input variables
        self.nodes = nodes
        self.links = links

        # check node dictionary contains required lists
        if not all(key in self.nodes for key in ["labels", "x"]):
            raise ValueError("Node dictionary must contain 'labels' and 'x' lists.")

        # check node dictionary contains lists with the same length
        if not all(len(self.nodes[key]) == len(self.nodes["labels"]) for key in self.nodes if key != "labels"):
            raise ValueError("All lists in the node dictionary must have the same length.")
        
        # check links dictionary contains required lists
        if not all(key in self.links for key in ["sources", "targets", "values"]):
            raise ValueError("Link dictionary must contain 'sources', 'targets', and 'values' lists.")

        # check links dictionary contains lists with the same length
        if not all(len(self.links[key]) == len(self.links["sources"]) for key in self.links if key != "sources"):
            raise ValueError("All lists in the link dictionary must have the same length.")
        
        # set default values for node characteristics
        N = len(self.nodes["labels"])
        self.nodes["roots"] = [True] * N
        self.nodes["leaves"] = [True] * N
        self.nodes["inflows"] = [0] * N
        self.nodes["outflows"] = [0] * N
        self.nodes["y"] = [0] * N

        # loop for each link
        for i in range(len(self.links["sources"])):

            # node cannot be a root if it is targetted and cannot be a leaf if it is a source
            self.nodes["roots"][self.links["targets"][i]] = False
            self.nodes["leaves"][self.links["sources"][i]] = False
        
            # tally inflow and outflow
            self.nodes["outflows"][self.links["sources"][i]] += self.links["values"][i]
            self.nodes["inflows"][self.links["targets"][i]] += self.links["values"][i]

        # calculate values for each node as maximum of inflows and outflows
        self.nodes["values"] = [
            max(inflow, outflow) for inflow, outflow
            in zip(self.nodes["inflows"], self.nodes["outflows"])
        ]

        # get node outflow x-coordinate
        self.nodes["x_out"] = [x + self.width for x in self.nodes["x"]]

        # loop for each column of sankey values
        for x in sorted(set(self.nodes["x"])):

            # get indices of all nodes corresponding to the given x-value
            indices = [i for i, j in enumerate(self.nodes["x"]) if j == x]

            # set first node 
            self.nodes["y"][indices[0]] = 0

            # loop for each index
            for i, j in zip(indices[:-1], indices[1:]):

                # set y-value of node
                self.nodes["y"][j] = self.nodes["y"][i] + self.nodes["values"][i] + self.y_margin

        # get node inflow and outflow y-coordinates to be updated later
        self.nodes["y_in"] = [y for y in self.nodes["y"]]
        self.nodes["y_out"] = [y for y in self.nodes["y"]]

        # create empty lists of splines
        self.links["lower_splines"] = []
        self.links["upper_splines"] = []

        # loop for each link
        for i in range(len(self.links["sources"])):

            # fit lower cubic polynomial and save coefficients
            spline = make_interp_spline(
                x = [
                    self.nodes["x_out"][self.links["sources"][i]],
                    self.nodes["x"][self.links["targets"][i]]
                ],
                y = [
                    self.nodes["y_out"][self.links["sources"][i]],
                    self.nodes["y_in"][self.links["targets"][i]]
                ],
                k = 3, bc_type = "clamped"
            )
            self.links["lower_splines"].append(spline)

            # fit upper cubic polynomial and save coefficients
            spline = make_interp_spline(
                x = [
                    self.nodes["x_out"][self.links["sources"][i]],
                    self.nodes["x"][self.links["targets"][i]]
                ],
                y = [
                    self.nodes["y_out"][self.links["sources"][i]] + self.links["values"][i],
                    self.nodes["y_in"][self.links["targets"][i]] + self.links["values"][i]
                ],
                k = 3, bc_type = "clamped"
            )
            self.links["upper_splines"].append(spline)

            # update y-values
            self.nodes["y_out"][self.links["sources"][i]] += self.links["values"][i]
            self.nodes["y_in"][self.links["targets"][i]] += self.links["values"][i]

    def __str__(self):
        """Returns a string representation of the Sankey class."""
        # string to return
        string = ""

        #
        string += "Nodes:\n"
        for key, value in self.nodes.items():

            string += f"{key}: {value}\n"

        string += "\nLinks:\n"
        for key, value in self.links.items():

            string += f"{key}: {value}\n"

        return string

    def plot(self, fig, ax):
        """Plots the sankey diagram on a given matplotlib figure and axis."""
        # loop for each node
        for i in range(len(self.nodes["labels"])):

            # add patch as rectangle and plot diagonal to update axis limits
            patch = Rectangle(
                xy = (self.nodes["x"][i], self.nodes["y"][i]),
                width = self.nodes["x_out"][i] - self.nodes["x"][i],
                height = self.nodes["values"][i],
                edgecolor = "k",
                linewidth = plt.rcParams["lines.linewidth"]
            )
            ax.add_patch(patch)
            ax.text(
                self.nodes["x"][i] + 0.5 * (self.nodes["x_out"][i] - self.nodes["x"][i]),
                self.nodes["y"][i] + 0.5 * self.nodes["values"][i],
                self.nodes["labels"][i],
                ha = "center",
                va = "center",
                color = "k"
            )
            ax.plot(
                [self.nodes["x"][i], self.nodes["x_out"][i]],
                [self.nodes["y"][i], self.nodes["y"][i] + self.nodes["values"][i]],
                linestyle = "",
                color = "k"
            )

        # loop for each link
        for i in range(len(self.links["sources"])):

            # get list of x-values
            xx = np.linspace(
                self.nodes["x_out"][self.links["sources"][i]],
                self.nodes["x"][self.links["targets"][i]], self.N
            )

            # plot lower spline
            spline = self.links["lower_splines"][i]
            ax.plot(xx, spline(xx), color = "k")

            # plot lower spline
            spline = self.links["upper_splines"][i]
            ax.plot(xx, spline(xx), color = "k")

        # configure plot
        ax.axis("off")

# main function
def main():

    # create sankey chart
    nodes = {
        "labels": ["hi", "hello", "hey", "alright", "yo", "A", "B", "C"],
        "x": [0, 1, 1, 2, 2, 3, 3, 3]
    }
    links = {
        "sources": [0, 0, 1, 2, 2, 3, 3, 3, 4],
        "targets": [1, 2, 3, 3, 4, 5, 6, 7, 7],
        "values": [1, 2, 1, 1.5, 0.5, 0.6, 0.8, 1.1, 0.5]
    }
    sankey = Sankey(nodes, links)

    print(sankey)
    
    # create plot
    fig, ax = plt.subplots()
    sankey.plot(fig, ax)

# upon script execution
if __name__ == "__main__":

    # run main and show all plots
    main()
    plt.show()
