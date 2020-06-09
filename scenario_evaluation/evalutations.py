class Evaluation:
    scenarios = None

    def __init__(self, *args, **kwargs):
        self.scenarios = kwargs.get('scenarios')
