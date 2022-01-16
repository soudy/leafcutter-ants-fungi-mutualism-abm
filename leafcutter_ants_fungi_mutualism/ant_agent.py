from .random_walker_agent import RandomWalkerAgent
from .plant import Plant
from .pheromone import Pheromone
from .util import manhattan_distance

import numpy as np
from enum import Enum, auto


class AntWorkerState(Enum):
    EXPLORE = auto()
    RECRUIT = auto()
    HARVEST = auto()


class AntAgent(RandomWalkerAgent):
    def __init__(self, unique_id, model):
        self.unique_id = unique_id
        super().__init__(unique_id, model)

        self.state = AntWorkerState.EXPLORE
        self.has_leaf = False

    def step(self):
        if self.state == AntWorkerState.EXPLORE:
            self.explore_step()
        elif self.state == AntWorkerState.RECRUIT:
            self.recruit_step()
        elif self.state == AntWorkerState.HARVEST:
            self.harvest_step()

    def explore_step(self):
        """
        When in explore state, the worker ant does a random walk until one of
        the following events occurs:
        1. It finds a pheromone and switches to harvest state in which it
           will follow the pherome trail to the plant and return a leaf to the
           nest.
        2. It finds a plant, after which it will switch to recruit mode to
           alert other ants of the location of the plant.
        If it finds both, it will go into one of two states probabilistically.
        """
        self.random_move()

        neighbors = self.model.grid.get_neighbors(self.pos, moore=True)
        nearby_plants = [p for p in neighbors if isinstance(p, Plant)]
        nearby_pheromones = [p for p in neighbors if isinstance(p, Pheromone)]

        if nearby_plants and nearby_pheromones:
            # both plant and pheromone in neighborhood, randomly choose state to
            # go to.
            self.state = self.random.choice([
                AntWorkerState.RECRUIT, AntWorkerState.HARVEST])
        elif nearby_plants:
            plant = self.random.choice(nearby_plants)
            plant.take_leaf()
            self.has_leaf = True
            self.state = AntWorkerState.RECRUIT
        elif nearby_pheromones:
            # XXX: should following state transition happen probabilistically to
            # ensure that some ants still explore?
            self.state = AntWorkerState.HARVEST

    def recruit_step(self):
        """
        In the recruit state, the ant returns to the hive in a straight line
        (using its memory/sensing abilities) while leaving a pheromone trail for
        other ants to find and harvest the plant.
        """
        if self.pos == self.model.nest_pos:
            # found nest, task of laying pheromone trail complete, return to
            # explore state
            self.state = AntWorkerState.EXPLORE
            return

        # leave pheromone on current location
        # TODO: should this have some extra energy cost?
        self.put_pheromone()

        # step towards nest
        x_step, y_step = self.get_direction_towards_nest()
        self.model.grid.move_agent(
            self, (self.pos[0] + x_step, self.pos[1] + y_step))

    def harvest_step(self):
        """
        In the harvest state, the ant follows the trail of pheromones towards
        the plant. If it arrives at a plant, it will cut a piece of leaf off and
        carry it to the nest to feed the fungus.
        """
        if self.has_leaf:
            # XXX: should the ant renew the pheromones when returning? maybe
            #   increment the pheromone lifetime by a small amount if it
            #   has succesfully gathered a leaf from it?

            # return to nest with leaf
            if self.pos == self.model.nest_pos:
                # found nest, feed fungus
                # TODO: now assumes we have just a single fungus, decide on how
                #   to handle fungi
                self.model.fungi[0].feed()
                self.has_leaf = False
                self.state = AntWorkerState.EXPLORE
                return

            x_step, y_step = self.get_direction_towards_nest()
            self.model.grid.move_agent(
                self, (self.pos[0] + x_step, self.pos[1] + y_step))
        else:
            neighbors = self.model.grid.get_neighbors(self.pos, moore=True)

            nearby_plants = [p for p in neighbors if isinstance(p, Plant)]
            if nearby_plants:
                # found plant, get leaf
                plant = self.random.choice(nearby_plants)
                plant.take_leaf()
                self.has_leaf = True
                return

            # follow pheromone trail
            nearby_pheromones = [
                p for p in neighbors if isinstance(p, Pheromone)]
            if not nearby_pheromones:
                # pheromones disappeared
                self.state = AntWorkerState.EXPLORE
                return

            # follow trail outwards from the nest towards the plant
            # XXX: is this the best way to do this?
            pheromones_dists = [manhattan_distance(p.pos, self.model.nest_pos)
                                for p in nearby_pheromones]
            outwards_pheromone = nearby_pheromones[np.argmax(pheromones_dists)]
            if manhattan_distance(outwards_pheromone.pos, self.model.nest_pos) < \
               manhattan_distance(self.pos, self.model.nest_pos):
                # XXX: if there is no plant anymore at the end of a pheromone trail
                #   (or the trail is shortened due to decaying pheromones), the ant
                #   will dance around the end of the pheromone trail until it is
                #   fully decayed. i'm not sure if this is observed in real ants or
                #   whether this is going to be a problem. this currently fixes this
                #   by never moving to a pheromone if it brings the ant closer to the
                #   nest. it will move to a random non-pheromone square instead to try
                #   and escape the bad pheromone trail
                neighborhood = self.model.grid.get_neighborhood(
                    self.pos, moore=True)
                self.random.shuffle(neighborhood)
                no_pheromone_neighbor = None
                for neighbor in neighborhood:
                    neighbor_agents = self.model.grid.get_cell_list_contents(
                        neighbor)
                    for agent in neighbor_agents:
                        if isinstance(agent, Pheromone):
                            break
                    else:
                        no_pheromone_neighbor = neighbor

                if no_pheromone_neighbor:
                    self.model.grid.move_agent(self, no_pheromone_neighbor)
                else:
                    # all neighbors have pheromones on them, do a random move
                    # (unlikely but possible)
                    self.random_move()
            else:
                self.model.grid.move_agent(self, outwards_pheromone.pos)

    def put_pheromone(self):
        """
        Put a pheromone on the current position of the ant.
        """
        agent = Pheromone(self.model.next_id(), self.model)
        self.model.schedule.add(agent)
        self.model.grid.place_agent(agent, self.pos)

    def get_direction_towards_nest(self):
        """
        Get the direction tuple towards the nest. Returns a tuple with the
        first element corresponding to the x direction and the second element
        corresponding to the y direction. Directions are in {-1, 0, 1}.
        """
        nest_x, nest_y = self.model.nest_pos
        self_x, self_y = self.pos

        angle = np.arctan2(nest_x - self_x, nest_y - self_y)
        x_step = round(np.sin(angle))
        y_step = round(np.cos(angle))

        return (x_step, y_step)
