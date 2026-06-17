# sankey.py
# 10 June 2026

# import modules
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.interpolate import make_interp_spline
from itertools import permutations, product

# import Colours class
from utils import Colours

# Inputs class
class Inputs:
    """Container for default values."""
    # diagram appearance constants
    alpha = 0.4

# Sankey class
class Sankey:
    """Class for creating a sankey diagram."""
    # constant values
    y_margin = 1
    width = 0.5
    N = 100

    def __init__(self, nodes, links):
        """Creates an instance of the Sankey class."""
        # store input variables
        self.nodes = nodes
        self.links = links

        # check for invalid inputs
        self.check_for_errors()

        # populate dictionaries with derived values
        self.fill_dictionaries()

        # construct sankey diagram
        self.build_chart()

    def __str__(self):
        """Returns a string representation of the Sankey class."""
        # string to return
        string = ""

        #
        string += "Nodes:\n"

        if isinstance(self.nodes, dict):
            for key, value in self.nodes.items():

                string += f"{key}: {value}\n"

        else:
            for node in self.nodes:

                string += f"{node}\n"

        string += "\nLinks:\n"
        for key, value in self.links.items():

            string += f"{key}: {value}\n"

        return string

    def fill_dictionaries(self):
        """Populates the input dictionaries with derived values."""        
        # set default values for node characteristics
        N = len(self.nodes["labels"])
        self.nodes["roots"] = [True] * N
        self.nodes["leaves"] = [True] * N
        self.nodes["inflows"] = [0] * N
        self.nodes["outflows"] = [0] * N
        self.nodes["y"] = [None] * N
        self.nodes["y_in"] = [None] * N
        self.nodes["y_out"] = [None] * N

        # create empty lists of splines
        M = len(self.links["values"])
        self.links["lower_splines"] = [None] * M
        self.links["upper_splines"] = [None] * M

        # loop for each link
        for i in range(len(self.links["sources"])):

            # node cannot be a root if it is targeted and cannot be a leaf if it is a source
            self.nodes["roots"][self.links["targets"][i]] = False
            self.nodes["leaves"][self.links["sources"][i]] = False
        
            # tally inflows and outflows
            self.nodes["outflows"][self.links["sources"][i]] += self.links["values"][i]
            self.nodes["inflows"][self.links["targets"][i]] += self.links["values"][i]

        # calculate values for each node as maximum of inflows and outflows
        self.nodes["values"] = [
            max(inflow, outflow) for inflow, outflow
            in zip(self.nodes["inflows"], self.nodes["outflows"])
        ]

        # get node outflow x-coordinate
        self.nodes["x_out"] = [x + self.width for x in self.nodes["x"]]

        # assign columns by grouping nodes whose x-extents overlap
        self.nodes["columns"] = [-1] * N
        column_id = 0

        # sort nodes by x-position
        node_order = sorted(range(N), key = lambda i: self.nodes["x"][i])

        # loop over nodes from left-to-right
        for i in node_order:

            # node already has column assigned to it
            if self.nodes["columns"][i] != -1:

                # do nothing
                continue

            # start a new column with this node
            self.nodes["columns"][i] = column_id
            col_x_end = self.nodes["x_out"][i]

            # infinite while loop
            changed = True
            while changed:

                # set loop variable to False and loop for each sorted node
                changed = False
                for j in node_order:

                    # node already has a column
                    if self.nodes["columns"][j] != -1:

                        # do nothing
                        continue

                    # node lies in given column
                    if self.nodes["x"][j] < col_x_end and self.nodes["x_out"][j] > self.nodes["x"][i]:

                        # assign node to that column and continue to loop
                        self.nodes["columns"][j] = column_id
                        col_x_end = max(col_x_end, self.nodes["x_out"][j])
                        changed = True

            # increment column id
            column_id += 1

    def check_for_errors(self):
        """Checks for various forms of invalid input and provides user feedback."""
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
            
        # check if all sources and targets are given as integers OR strings
        if all(isinstance(x, (int, str)) for x in self.links["sources"] + self.links["targets"]):

            # loop for all sources
            for i, string in enumerate(self.links["sources"]):

                # check if source is given as a string
                if isinstance(string, str):
            
                    # replace source with corresponding integer code
                    self.links["sources"][i] = self.nodes["labels"].index(string)

            # loop for all targets
            for i, string in enumerate(self.links["targets"]):

                # check if target is given as a string
                if isinstance(string, str):

                    # replace target with corresponding integer code
                    self.links["targets"][i] = self.nodes["labels"].index(string)

            # check if any integers given are out of bounds
            if any(x > len(self.nodes["labels"]) - 1 for x in self.links["sources"] + self.links["targets"]):
                raise ValueError("Integer code for sources/targets is out of bounds!")

        # an unknown datatype was received
        else:

            raise ValueError("Unknown data type received!")

    def build_chart(self):
        """Assigns nodes to groups and finds node vertical positions to minimise crossings."""
        # get all root indices and sort by values (large to small)
        root_indices = [i for i in range(len(self.nodes["labels"])) if self.nodes["roots"][i]]
        root_indices.sort(key = lambda idx: self.nodes["values"][idx], reverse = True)

        # counter for group ids
        self.group_id = 0
        self.nodes["groups"] = [None] * len(self.nodes["labels"])

        # loop for each root node
        for root_index in root_indices:

            # set group id
            self.nodes["groups"][root_index] = self.group_id

            # increment counter
            self.group_id += 1

            # assign children to a group
            self.assign_groups(root_index)

        # create list of columns
        self.columns = []

        # loop for each column
        N = len(self.nodes["labels"])
        columns = sorted(set([self.nodes["columns"][i] for i in range(N)]))
        for column in columns:

            # get indices of all nodes in column
            nodes = [i for i, value in enumerate(self.nodes["columns"]) if value == column]

            # store column with spatial information
            self.columns.append(Column(
                x = min([self.nodes["x"][i] for i in nodes]),
                width = max([self.nodes["x"][i] for i in nodes]) - min([self.nodes["x"][i] for i in nodes]) + self.width,
                min_height = sum([self.nodes["values"][i] for i in nodes])
            ))

            # get all groups in column
            groups = sorted(set([
                self.nodes["groups"][i] for i, value in enumerate(self.nodes["columns"])
                if value == column
            ]))

            # loop for each group in the column
            for group in groups:

                # get indices of all nodes in group
                nodes = [index for index, value in enumerate(self.nodes["groups"]) if value == group]

                # store group with spatial information
                self.columns[-1].groups.append(Group(
                    x = min([self.nodes["x"][i] for i in nodes]),
                    width = max([self.nodes["x"][i] for i in nodes]) - min([self.nodes["x"][i] for i in nodes]) + self.width,
                    min_height = sum([self.nodes["values"][i] for i in nodes])
                ))

                # loop for each node in the group
                for node in nodes:

                    # create empty dictionary and loop for each key in the input dictionary
                    dict = {"index": node}
                    for key, _ in self.nodes.items():

                        # store i-th value of input dictionary
                        dict[key] = self.nodes[key][node]

                    # save and store node
                    self.columns[-1].groups[-1].nodes.append(Node(dict))

        # replace nodes dictionary with list of Node objects. loop for each column
        self.nodes = [None] * N
        for column in self.columns:

            # loop for each group
            for group in column.groups:

                # loop for each node
                for node in group.nodes:

                    # store node in list of nodes
                    self.nodes[node.index] = node

        # get list of permutations for each column
        permutations = [list(column.permutations()) for column in self.columns]

        # counter for the lowest number of crossings
        min_crossings = np.inf
        tiebreaker = np.inf
        best_layout = None

        # loop for each layout permutation
        for layout in product(*permutations):

            # draw layout and store number of crossings
            crossings, weighted_sum = self.draw_layout(layout)

            # check if number of crossings is reduced
            if crossings < min_crossings:

                # store layout and update best number of crossings and weighted sum
                best_layout = layout
                min_crossings = crossings
                tiebreaker = weighted_sum

            # number of crossings equals best
            elif crossings == min_crossings:

                # check if sum of node values weighted by y-position is less than tiebreaker value
                if weighted_sum < tiebreaker:

                    # store layout and update best number of crossings and weighted sum
                    best_layout = layout
                    min_crossings = crossings
                    tiebreaker = weighted_sum

        # redraw sankey diagram with best layout
        self.draw_layout(best_layout)

    def assign_groups(self, root_index):
        """Recurses to assign each child of a given node to a group."""
        # find all children of the node
        link_indices = [j for j, value in enumerate(self.links["sources"]) if value == root_index]
        children = [self.links["targets"][j] for j in link_indices]

        # loop for each column in the children set
        for column in sorted(set([self.nodes["columns"][j] for j in children])):

            # get all children with that column
            indices = [j for j in children if self.nodes["columns"][j] == column]

            # assign to the same group
            for index in indices:

                # node does not yet have a group
                if self.nodes["groups"][index] == None:

                    # set group
                    self.nodes["groups"][index] = self.group_id

            # increment counter
            self.group_id += 1

        # loop for each child node
        for child in children:

            # assign recursively to groups
            self.assign_groups(child)

    def draw_layout(self, layout):
        """Draws the layout of nodes and links given a specific ordering of groups and nodes."""
        # loop for each column
        for column, group_nodes in zip(self.columns, layout):

            # initialise counter for column height
            column.y = -0.5 * column.min_height

            # loop for group-node tuples stored in the column
            for group, nodes in group_nodes:

                # store group y-value
                group.y = column.y

                # loop for each node
                for node in nodes:

                    # set node y-value to column y-counter and increment
                    node.y = column.y
                    column.y += node.values + self.y_margin

        # loop for all nodes
        for node in self.nodes:
            
            node.y_in = node.y
            node.y_out = node.y

        # counter for the number of crossings
        crossings = 0

        # loop for each column
        for column in self.columns:

            # initialise y-counter for checking crossings against
            y_out = -np.inf

            # loop for each group in y-order
            for group in sorted(column.groups, key = lambda g: g.y):

                # loop for each node in y-order
                for node in sorted(group.nodes, key = lambda n: n.y):

                    # get all links with that node as source
                    links = [index for index, value in enumerate(self.links["sources"]) if value == node.index]
                    
                    # get target indices
                    target_indices = [self.links["targets"][index] for index in links]

                    # get target y-values
                    target_y = [self.nodes[index].y for index in target_indices]

                    # loop for each link
                    for index, target_index, _ in sorted(
                        zip(links, target_indices, target_y),
                        key = lambda x: x[2],
                        reverse = False
                    ):

                        # fit cubic splines
                        self.draw_flow(index, node.index, target_index)

                        # drawn flow is a crossing
                        if self.nodes[target_index].y_in < y_out:

                            # increment number of crossings
                            crossings += 1

                        # update y-value to check crossings against
                        y_out = max(y_out, self.nodes[target_index].y_in)

        # calculate weighted sum of node positions
        weighted_sum = sum([node.values * node.y for node in self.nodes])

        # return number of crossings and sum of node values weighted by y-positions
        return crossings, weighted_sum

    def draw_flow(self, index, source_index, target_index):
        """Fits two cubics from from one node to another, spaced apart by the magnitude of the flow."""
        # fit lower cubic polynomial and save coefficients
        spline = make_interp_spline(
            x = [
                self.nodes[source_index].x_out,
                self.nodes[target_index].x
            ],
            y = [
                self.nodes[source_index].y_out,
                self.nodes[target_index].y_in
            ],
            k = 3, bc_type = "clamped"
        )
        self.links["lower_splines"][index] = spline

        # fit upper cubic polynomial and save coefficients
        spline = make_interp_spline(
            x = [
                self.nodes[source_index].x_out,
                self.nodes[target_index].x
            ],
            y = [
                self.nodes[source_index].y_out
                + self.links["values"][index],
                self.nodes[target_index].y_in
                + self.links["values"][index]
            ],
            k = 3, bc_type = "clamped"
        )
        self.links["upper_splines"][index] = spline

        # update y-values
        self.nodes[source_index].y_out += self.links["values"][index]
        self.nodes[target_index].y_in += self.links["values"][index]

    def plot(self, fig, ax):
        """Plots the sankey diagram on a given matplotlib figure and axis."""
        # loop for each node
        for index in range(len(self.nodes)):

            # add patch as rectangle and plot diagonal to update axis limits
            patch = Rectangle(
                xy = (self.nodes[index].x, self.nodes[index].y),
                width = self.nodes[index].x_out - self.nodes[index].x,
                height = self.nodes[index].values,
                edgecolor = "k",
                linewidth = plt.rcParams["lines.linewidth"],
                facecolor = self.nodes[index].colours
            )
            ax.add_patch(patch)
            ax.plot(
                [self.nodes[index].x, self.nodes[index].x_out],
                [self.nodes[index].y, self.nodes[index].y + self.nodes[index].values],
                linestyle = "",
                color = "k"
            )

            # overlay display text
            ax.text(
                self.nodes[index].x + 0.5 * (self.nodes[index].x_out - self.nodes[index].x),
                self.nodes[index].y + 0.5 * self.nodes[index].values,
                self.nodes[index].display_names,
                ha = "center",
                va = "center",
                color = "k"
            )

        # loop for each link
        for index in range(len(self.links["sources"])):

            # get source and target node indices
            source_index = self.links["sources"][index]
            target_index = self.links["targets"][index]

            # get list of x-values
            xx = np.linspace(
                self.nodes[source_index].x_out,
                self.nodes[target_index].x, self.N
            )

            # plot lower spline
            lower_spline = self.links["lower_splines"][index]
            ax.plot(xx, lower_spline(xx), color = "k")

            # plot lower spline
            upper_spline = self.links["upper_splines"][index]
            ax.plot(xx, upper_spline(xx), color = "k")

            # loop for each 
            for (x_1, x_2) in zip(xx[1:], xx[:-1]):

                continue

                # fill region between splines
                ax.fill_between(
                    [x_1, x_2], lower_spline([x_1, x_2]), upper_spline([x_1, x_2]),
                    color = self.nodes[source_index].colours,
                    alpha = 0.5 * Inputs.alpha * (max(xx) - x_1) / (max(xx) - min(xx))
                )
                ax.fill_between(
                    [x_1, x_2], lower_spline([x_1, x_2]), upper_spline([x_1, x_2]),
                    color = self.nodes[target_index].colours,
                    alpha = 0.5 * Inputs.alpha * (x_1 - min(xx)) / (max(xx) - min(xx))
                )

        # configure plot
        ax.axis("off")

# Node class
class Node:
    """Stores properties for a node in the Sankey diagram."""
    def __init__(self, dict):
        """Creates an instance of the Node class."""
        # loop for each key in the input dictionary
        for key, value in dict.items():

            # store attribute
            setattr(self, key, value)

        # store colour
        self.colours = "C0"

    def __str__(self):
        """Returns a string representation of the class instance."""
        # initialise empty string and loop for all class instance attributes
        string = ""
        for attribute, value in self.__dict__.items():

            # append attribute-value pairs to string
            string += f"{attribute}: {value}\n"

        return string

# Container class
class Container:
    """Parent class for the Group and Column classes."""
    def __init__(self, x, width, min_height):
        """Creates an instance of the Container class."""
        # store input variables
        self.x = x
        self.width = width
        self.min_height = min_height

    def __str__(self):
        """Returns a string representation of the class instance."""
        # initialise empty string and loop for all class instance attributes
        string = ""
        for attribute, value in self.__dict__.items():

            # append attribute-value pairs to string
            string += f"{attribute}: {value}\n"

        return string

# Group class
class Group(Container):
    """Stores properties for a grouping of nodes in the Sankey diagram."""
    def __init__(self, x, width, min_height):
        # save input variables via parent class
        super().__init__(x, width, min_height)

        # initialise empty list of nodes
        self.nodes = []

    def permutations(self):
        """Yields all orderings of this group's nodes as lists."""
        for node_order in permutations(self.nodes):
            yield list(node_order)

# Column class
class Column(Container):
    """Stores properties for a column in the Sankey diagram, with groups as children."""
    def __init__(self, x, width, min_height):
        """Creates an instance of the Column class."""
        # save input variables via parent class
        super().__init__(x, width, min_height)

        # initialise empty list of groups
        self.groups = []

    def permutations(self):
        """Yields all permutations of the column as a list of (Group, [Node, ...]) tuples."""
        # all orderings of the groups list
        for group_order in permutations(self.groups):

            # for each group ordering, collect all possible node orderings per group
            node_perm_options = [list(g.permutations()) for g in group_order]

            # cartesian product: one node ordering per group
            for node_orders in product(*node_perm_options):
                yield [
                    (group, node_order)
                    for group, node_order in zip(group_order, node_orders)
                ]

# main function
def main():

    # create sankey chart
    nodes = {
        "labels": ["hi", "hello", "hey", "alright", "yo", "A", "B", "C", "sup"],
        "x": [0, 0.8, 1, 2, 2, 3, 3, 3, 0]
    }
    links = {
        "sources": [0, 0, 1, 2, 2, 3, 3, 3, 4, "sup"],
        "targets": [1, 2, 3, 3, 4, 5, 6, 7, "C", "hello"],
        "values": [1, 2, 2, 1.5, 0.5, 0.6, 1.8, 1.1, 0.5, 1]
    }
    nodes["display_names"] = nodes["labels"]
    sankey = Sankey(nodes, links)

    #print(sankey)
    
    # create plot
    fig, ax = plt.subplots()
    sankey.plot(fig, ax)

# upon script execution
if __name__ == "__main__":

    # run main and show all plots
    main()
    plt.show()
