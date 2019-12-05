import logging
from importlib import import_module
from typing import Tuple

import absl.logging

import numpy as np

from sklearn import preprocessing

# This gets rid of tensorflow warnings that we don't want to see.
logging.getLogger("tensorflow").setLevel(logging.ERROR)
absl.logging._warn_preinit_stderr = False


class KeywordDetector:
    """
    Exposes a tensorflow saved model for decoding.
    """

    def __init__(
        self,
        model_path: str,
        mfcc_node_name: str,
        predicted_indices_node_name: str,
        logits_output_node_name: str,
        drop_first_mfcc: bool,
        preemphasis: bool,
        normalise: bool,
        batch_norm: bool,
    ):
        """
        Creates a new KeywordDetector instance.
        :param model_path: The path to a model directory.
        :param mfcc_node_name: Name of mfcc node.
        :param predicted_indices_node_name: Name of predicited indices node.
        :param logits_output_node_name: Name of logits output node.
        :param drop_first_mfcc: Drop first value from each frame of mfccs.
        :param preemphasis: Apply preemphasis to the input.
        :param normalise: Normalise the input.
        :param batch_norm: Run batch normalisation on the input.
        """
        self._tf = import_module('tensorflow')
        self._load_session(model_path)
        self.mfcc_node = self.sess.graph.get_tensor_by_name(mfcc_node_name)
        self.predicted_indices_node = self.sess.graph.get_tensor_by_name(
            predicted_indices_node_name
        )
        self.logits_output_node = self.sess.graph.get_tensor_by_name(
            logits_output_node_name
        )
        self._drop_first_mfcc = drop_first_mfcc
        self._preemphasis = preemphasis
        self._normalise = normalise
        self._batch_norm = batch_norm

    def _load_session(self, model_path: str) -> None:
        """
        Loads Tensorflow Session from saved model.
        :param model_path: Path to model directory.
        """
        model_graph = self._tf.Graph()
        self.sess = self._tf.compat.v1.Session(graph=model_graph)
        self._tf.compat.v1.saved_model.load(
            self.sess, [self._tf.saved_model.SERVING], model_path
        )

    def _apply_preemphasis(self, samples: np.ndarray, preemp_value=0.97):
        """
        Applies preemphasis (high-pass filter) to the input samples.
        :param samples: array of shape (16000, 0) representing 16k audio.
        :param preemp_value: coefficient for preemphasis.
        :return: Sample values after applying preemphasis.
        """
        output = np.subtract(
            samples, preemp_value * np.concatenate(([0.0], samples[:-1]))
        )
        output[0] = 0
        return output

    def _mfcc_as_frames(self, mfcc: np.ndarray) -> np.ndarray:
        """
        Reshape extracted MFCCs to the frame size needed by the model.
        NB: When decoding one window at a time, this is equivalent to
            mfcc = np.expand_dims(mfcc, 0).
        :param mfcc: Array of extracted features of shape (num_frames, num_mfccs).
        :return: MFCCs with extra dimension added which can be passed to the model for decoding.
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

    def decode(self, samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extracts features from the input sample array and decodes it with the model.
        :param samples: array of shape (16000, ) representing one frame of 16k audio.
        :return: Logits and softmax probabilities.
        """
        if self._preemphasis:
            samples = self._apply_preemphasis(samples)
        if len(samples.shape) == 1:
            samples = np.expand_dims(samples, axis=-1)
        assert len(samples.shape) == 2

        # extract mfcc features
        feed_dict = {"sample_input:0": samples}
        mfcc = self.sess.run(self.mfcc_node, feed_dict=feed_dict)
        if len(mfcc.shape) == 3 and mfcc.shape[0] == 1:
            mfcc = np.squeeze(mfcc, axis=0)
        if self._drop_first_mfcc:
            mfcc = mfcc[:, 1:]
        if self._normalise:
            mfcc = preprocessing.scale(mfcc, axis=1)
        mfcc = self._mfcc_as_frames(mfcc)

        # keyword detection
        assert len(mfcc.shape) == 3
        if self._batch_norm:
            feed_dict = {"input:0": mfcc, "is_train:0": False}
        else:
            feed_dict = {"input:0": mfcc, "dropout_prob:0": 1.0}
        predictions, logits = self.sess.run(
            [self.predicted_indices_node, self.logits_output_node], feed_dict=feed_dict
        )
        return logits, predictions
