import tensorflow as tf
import numpy as np
from sklearn import preprocessing
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

class KeywordDetector():
    """
    Exposes a trained wakeword .pb frozen Tensorflow graph for decoding.

    Args:
        model_path (str): Path to model dir.
        drop_first_mfcc (bool): If True, model requires that the 0th MFCC is discarded.
        preemphasis (bool): If True, model requires that preemphasis is applied before
            feature extraction.
        normalise (bool): If True, model requires that features are normalised.
        batch_norm (bool): If True, model was trained with batch normalisation.
    """

    def __init__(self, model_path: str, mfcc_node_name: str, predicted_indices_node_name: str, logits_output_node_name: str, drop_first_mfcc: bool, preemphasis: bool, normalise: bool, batch_norm: bool):
        self._load_session(model_path)

        self.mfcc_node = self.sess.graph.get_tensor_by_name(mfcc_node_name)
        self.predicted_indices_node = self.sess.graph.get_tensor_by_name(predicted_indices_node_name)
        self.logits_output_node = self.sess.graph.get_tensor_by_name(logits_output_node_name)

        self._drop_first_mfcc = drop_first_mfcc
        self._preemphasis = preemphasis
        self._normalise = normalise
        self._batch_norm = batch_norm

    def _load_session(self, model_path):
        model_graph = tf.Graph()
        self.sess = tf.compat.v1.Session(graph = model_graph)
        _meta_graph_def = tf.compat.v1.saved_model.load(
            self.sess, [tf.saved_model.SERVING], model_path
        )

    def _apply_preemphasis(self, samples: np.ndarray, preemp_value = 0.97):
        """
        Applies preemphasis (high-pass filter) to the input samples.

        Args:
            samples (np.ndarray): array of shape (16000, 0) representing 16k audio.
            preemp_value (float): coefficient for preemphasis.

        Returns:
            np.ndarray: Sample values after applying preemphasis.
        """
        output = np.subtract(samples, preemp_value * np.concatenate(([0.], samples[:-1])))
        output[0] = 0
        return output

    def _mfcc_as_frames(self, mfcc: np.ndarray):
        """
        Reshape extracted MFCCs to the frame size needed by the model.
        NB: When decoding one window at a time, this is equivalent to
            mfcc = np.expand_dims(mfcc, 0).

        Args:
            mfcc (np.ndarray): Array of extracted features of shape (num_frames, num_mfccs).

        Returns:
            MFCCs with extra dimension added which can be passed to the model for decoding.
        """
        num_mfccs_for_window = mfcc.shape[0]
        s0, s1 = mfcc.strides

        return np.lib.stride_tricks.as_strided(
            mfcc,
            shape=(
                (mfcc.shape[0] - num_mfccs_for_window + 1),
                num_mfccs_for_window,
                mfcc.shape[-1],
            ),
            strides=(s0, s0, s1),
        )

    def decode(self, samples: np.ndarray):
        """
        Extracts features from the input sample array and decodes it with the model.

        Args:
            samples (np.ndarray): array of shape (16000, ) representing one
                frame of 16k audio.

        Returns:
            tuple: Logits and softmax probabilities.
        """
        if self._preemphasis:
            samples = self._apply_preemphasis(samples)

        if len(samples.shape) == 1:
            samples = np.expand_dims(samples, axis = -1)
        assert (len(samples.shape) == 2)

        #extract mfcc features
        feed_dict = {'sample_input:0': samples}
        mfcc = self.sess.run(self.mfcc_node, feed_dict=feed_dict)

        if len(mfcc.shape) == 3 and mfcc.shape[0] == 1:
            mfcc = np.squeeze(mfcc, axis = 0)

        if self._drop_first_mfcc:
            mfcc = mfcc[:,1:]

        if self._normalise:
            mfcc = preprocessing.scale(mfcc, axis = 1)

        mfcc = self._mfcc_as_frames(mfcc)

        #keyword detection
        assert (len(mfcc.shape) == 3)

        if self._batch_norm:
            feed_dict = {'input:0': mfcc, 'is_train:0': False}
        else:
            feed_dict = {'input:0': mfcc, 'dropout_prob:0': 1.0}
        predictions, logits = self.sess.run([self.predicted_indices_node, self.logits_output_node], feed_dict=feed_dict)
        return logits, predictions
