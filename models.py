from structure import property_wrap


class Model:
    def __init__(self, data=None, batch_size=None,
                 testing=False, learning_rate=1e-4):
        self.data = data
        self.batch_size = batch_size
        self.testing = testing
        self.learning_rate = learning_rate

        self.global_step = None

        self._loss = None
        self._metric = None
        self._optimize = None
        self._prediction = None

    def _file_read_op(self, file_names, batch_size,
                      num_epochs, *args, **kwargs):
        pass

    def _network(self, *args, **kwargs):
        pass

    @property_wrap('_prediction')
    def prediction(self):
        return self._prediction

    @property_wrap('_loss')
    def loss(self):
        return self._loss

    @property_wrap('_metric')
    def metric(self):
        return self._metric

    @property_wrap('_optimize')
    def optimize(self):
        return self._optimize
