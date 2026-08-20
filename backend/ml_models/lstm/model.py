"""
A small, dependency-free LSTM implemented in NumPy.

Why hand-rolled instead of PyTorch/TensorFlow: the rest of this project only
depends on numpy/scikit-learn/joblib, and installing a full deep-learning
framework just to run a 10-step, 4-feature sequence classifier is overkill
for a prototype. This implementation is a single-layer LSTM -> sigmoid head,
trained with plain backpropagation-through-time (BPTT) and mini-batch
gradient descent. Weights are saved to / loaded from a .npz file, mirroring
how the Random Forest is stored as a .joblib file.

Input:  a (10, 4) window of the last 10 readings, each with
        [heart_rate, spo2, systolic_bp, diastolic_bp], min-max normalized.
Output: a single probability in [0, 1] that the patient is trending toward
        a high-risk state over the window (the "early warning" signal).
"""
import numpy as np


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))


class NumpyLSTM:
    def __init__(self, input_size=4, hidden_size=16, seed=42):
        self.input_size = input_size
        self.hidden_size = hidden_size
        rng = np.random.default_rng(seed)
        z = input_size + hidden_size
        scale = 1.0 / np.sqrt(hidden_size)

        # Combined weight matrices for forget / input / output / candidate gates.
        self.Wf = rng.uniform(-scale, scale, (hidden_size, z))
        self.Wi = rng.uniform(-scale, scale, (hidden_size, z))
        self.Wo = rng.uniform(-scale, scale, (hidden_size, z))
        self.Wg = rng.uniform(-scale, scale, (hidden_size, z))
        self.bf = np.ones((hidden_size, 1))  # forget-gate bias initialized to 1 (standard trick)
        self.bi = np.zeros((hidden_size, 1))
        self.bo = np.zeros((hidden_size, 1))
        self.bg = np.zeros((hidden_size, 1))

        self.Wy = rng.uniform(-scale, scale, (1, hidden_size))
        self.by = np.zeros((1, 1))

    # ---------------------------------------------------------------- #
    # Forward pass
    # ---------------------------------------------------------------- #
    def forward(self, x_seq):
        """x_seq: (T, input_size). Returns probability and cache for BPTT."""
        T = x_seq.shape[0]
        H = self.hidden_size
        h = np.zeros((H, 1))
        c = np.zeros((H, 1))
        cache = []

        for t in range(T):
            x_t = x_seq[t].reshape(-1, 1)
            z = np.vstack((h, x_t))
            f = sigmoid(self.Wf @ z + self.bf)
            i = sigmoid(self.Wi @ z + self.bi)
            o = sigmoid(self.Wo @ z + self.bo)
            g = np.tanh(self.Wg @ z + self.bg)
            c_new = f * c + i * g
            h_new = o * np.tanh(c_new)
            cache.append((z, f, i, o, g, c, c_new, h))
            c, h = c_new, h_new

        y = sigmoid(self.Wy @ h + self.by)
        return float(y.item()), h, cache

    def predict_proba(self, x_seq):
        prob, _, _ = self.forward(x_seq)
        return prob

    # ---------------------------------------------------------------- #
    # Backpropagation-through-time for one sequence
    # ---------------------------------------------------------------- #
    def _backward(self, x_seq, y_true, h_final, cache):
        H = self.hidden_size
        y_pred = sigmoid(self.Wy @ h_final + self.by)
        dy = (y_pred - y_true)  # d(BCE)/d(logit) for sigmoid output

        grads = {k: np.zeros_like(getattr(self, k)) for k in
                 ['Wf', 'Wi', 'Wo', 'Wg', 'bf', 'bi', 'bo', 'bg', 'Wy', 'by']}

        grads['Wy'] = dy @ h_final.T
        grads['by'] = dy

        dh_next = (self.Wy.T @ dy)
        dc_next = np.zeros((H, 1))

        for t in reversed(range(len(cache))):
            z, f, i, o, g, c_prev, c_new, h_prev = cache[t]
            dh = dh_next
            do = dh * np.tanh(c_new)
            do_raw = do * o * (1 - o)

            dc = dh * o * (1 - np.tanh(c_new) ** 2) + dc_next
            df = dc * c_prev
            df_raw = df * f * (1 - f)

            di = dc * g
            di_raw = di * i * (1 - i)

            dg = dc * i
            dg_raw = dg * (1 - g ** 2)

            grads['Wf'] += df_raw @ z.T
            grads['Wi'] += di_raw @ z.T
            grads['Wo'] += do_raw @ z.T
            grads['Wg'] += dg_raw @ z.T
            grads['bf'] += df_raw
            grads['bi'] += di_raw
            grads['bo'] += do_raw
            grads['bg'] += dg_raw

            dz = (self.Wf.T @ df_raw + self.Wi.T @ di_raw
                  + self.Wo.T @ do_raw + self.Wg.T @ dg_raw)
            dh_next = dz[:H]
            dc_next = dc * f

        loss = -(y_true * np.log(y_pred + 1e-9) + (1 - y_true) * np.log(1 - y_pred + 1e-9))
        return grads, float(loss.item())

    def train_step(self, x_seq, y_true, lr=0.05, clip=5.0):
        prob, h_final, cache = self.forward(x_seq)
        grads, loss = self._backward(x_seq, np.array([[y_true]]), h_final, cache)
        for name, grad in grads.items():
            np.clip(grad, -clip, clip, out=grad)
            setattr(self, name, getattr(self, name) - lr * grad)
        return loss

    # ---------------------------------------------------------------- #
    # Persistence
    # ---------------------------------------------------------------- #
    def save(self, path):
        np.savez(
            path,
            Wf=self.Wf, Wi=self.Wi, Wo=self.Wo, Wg=self.Wg,
            bf=self.bf, bi=self.bi, bo=self.bo, bg=self.bg,
            Wy=self.Wy, by=self.by,
            input_size=self.input_size, hidden_size=self.hidden_size,
        )

    @classmethod
    def load(cls, path):
        data = np.load(path)
        model = cls(input_size=int(data['input_size']), hidden_size=int(data['hidden_size']))
        for name in ['Wf', 'Wi', 'Wo', 'Wg', 'bf', 'bi', 'bo', 'bg', 'Wy', 'by']:
            setattr(model, name, data[name])
        return model
