from mesa import Agent
import queue
from .ant_agent import AntAgent, AntWorkerState


class Nest(Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.energy_buffer = 0.0
        self.fitness_queue = queue.Queue(self.model.max_fitness_queue_size)

    def ant_birth(self, n):
        fitness_queue_list = list(self.fitness_queue.queue)
        if len(fitness_queue_list) != 0:
            average_fitness = sum(fitness_queue_list)/len(fitness_queue_list)
        else:
            average_fitness = 0.5
        for _ in range(n):
            agent = AntAgent(self.model.next_id(), self.model)

            if self.random.random() > average_fitness:
                agent.state = AntWorkerState.CARETAKING

            self.model.schedule.add(agent)
            self.model.grid.place_agent(agent, self.pos)

    def feed_larvae(self):
        if not self.model.fungus.dead:
            self.model.fungus.biomass -= self.model.caretaker_carrying_amount
            # this feeding step might have killed the fungus already
            # so check for death
            self.model.fungus.check_death()
            self.energy_buffer += self.model.fungus_larvae_cvn * \
                self.model.caretaker_carrying_amount

    def step(self):
        offspring_count = int(self.energy_buffer /
                              self.model.energy_per_offspring)
        self.energy_buffer -= offspring_count * self.model.energy_per_offspring
        self.ant_birth(offspring_count)