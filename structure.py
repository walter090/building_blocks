from functools import wraps

import numpy as np
import tensorflow as tf


def property_wrap(attr):
    """Checks if the function has already been called

    Args:
        attr: string, attribute name the decorated function is supposed
            to return.

    Returns:
        function
    """

    def de_facto_wrap(func):
        @property
        @wraps(func)
        def decorator(self):
            if getattr(self, attr) is None:
                setattr(self, attr, func(self))
            return getattr(self, attr)

        return decorator

    return de_facto_wrap


def conv_pool(x, ksize=None, stride=None,
              out_channels=None, pool_ksize=None, pool_stride=None,
              alpha=0.1, padding='VALID', batchnorm=True,
              method='max', name='conv'):
    """Convolution layer with pooling

    Args:
        x: Input from the previous layer.
        ksize: tuple, filter size.
        stride: Stride for the convolution layer.
        out_channels: Out channels for the convnet.
        pool_ksize: Filter size for the average pooling layer.
        pool_stride: Stride for the average pooling layer.
        alpha: Parameter for Leaky ReLU.
        name: Name of the variable scope.
        padding: Padding for the layers, default 'VALID'.
        batchnorm: Set True to use batch normalization.
        method: string, set to max to use max pooling, avg to use average pooling.

    Returns:
        Convoluted tensor
    """
    with tf.variable_scope(name):
        weights = tf.get_variable(name='conv_w',
                                  shape=[ksize[0], ksize[1],
                                         x.get_shape().as_list()[3], out_channels],
                                  initializer=tf.random_normal_initializer())
        bias = tf.get_variable(name='conv_b',
                               shape=[out_channels],
                               initializer=tf.zeros_initializer())

        convoluted = tf.nn.convolution(x, filter=weights,
                                       strides=stride, padding=padding)
        convoluted = tf.nn.bias_add(convoluted, bias)

        if batchnorm:
            convoluted = batch_normalize(convoluted)

        output = lrelu(convoluted, alpha)

        if pool_ksize and pool_stride:
            pool_ksize = [1, *pool_ksize, 1]
            pool_stride = [1, *pool_stride, 1]

            if method == 'avg':
                output = tf.nn.avg_pool(output, ksize=pool_ksize,
                                        strides=pool_stride, padding=padding)
            elif method == 'max':
                output = tf.nn.max_pool(output, ksize=pool_ksize,
                                        strides=pool_stride, padding=padding)
            else:
                raise ValueError("Choose a pooling method between 'max' and 'avg.'")
        return output


def create_cell(num_layers, state_size, keep_prob, peepholes):
    """Function for creating a lstm cell.
    Args:
        num_layers: int, number of stacked lstm layers.
        state_size: int, size of state.
        keep_prob: float, keep probability for dropout.
        peepholes: bool, set True to use peephole connections.
    Returns:
        Tensor, lstm cell.
    """
    cell = tf.nn.rnn_cell.LSTMCell(num_units=state_size, use_peepholes=peepholes)
    cell = tf.nn.rnn_cell.DropoutWrapper(cell=cell, state_keep_prob=keep_prob,
                                         output_keep_prob=keep_prob, input_keep_prob=keep_prob)
    if num_layers > 1:
        cell = tf.nn.rnn_cell.MultiRNNCell([cell] * num_layers, state_is_tuple=True)

    return cell


def lstm(x, num_layers, keep_prob,
         state_size, peepholes, batch_size,
         sequence_length):
    """Create LSTM.

    Args:
        x: Tensor, input to network.
        num_layers: int, number of layers.
        keep_prob: float, keep probability for dropout.
        state_size: int, state size.
        peepholes: boolean, set True to use peephole connections.
        batch_size: int, size of each batch.
        sequence_length: tensor, batch sequence length.

    Returns:
        outputs: tensor, outputs from the network.
    """
    cell = create_cell(num_layers=num_layers, state_size=state_size,
                       keep_prob=keep_prob, peepholes=peepholes)

    init_state = cell.zero_state(batch_size=batch_size, dtype=tf.float32)

    outputs, _ = tf.nn.dynamic_rnn(cell=cell, inputs=x,
                                   sequence_length=sequence_length, initial_state=init_state)

    outputs = tf.reshape(outputs, [-1, state_size])
    return outputs


def bi_lstm(x, num_layers, keep_prob,
            state_size, peepholes, batch_size,
            sequence_length):
    cell_fw = create_cell(num_layers=num_layers, state_size=state_size,
                          keep_prob=keep_prob, peepholes=peepholes)
    cell_bw = create_cell(num_layers=num_layers, state_size=state_size,
                          keep_prob=keep_prob, peepholes=peepholes)
    init_state_fw = cell_fw.zero_state(batch_size=batch_size, dtype=tf.float32)
    init_state_bw = cell_fw.zero_state(batch_size=batch_size, dtype=tf.float32)

    birnn_outputs, _ = outputs, _ = tf.nn.bidirectional_dynamic_rnn(
        cell_fw=cell_fw, cell_bw=cell_bw,
        initial_state_fw=init_state_fw, initial_state_bw=init_state_bw,
        sequence_length=sequence_length, inputs=x
    )

    output_fw, output_bw = birnn_outputs

    outputs = tf.concat([output_fw, output_bw], axis=-1)
    return outputs


def get_last_hidden(batch_size, len_sequence, outputs,
                    sequence_length):
    """Get last hidden state.

    Args:
        batch_size: int, size of each batch.
        len_sequence: int, length of each sequence.
        outputs: tensor, outputs from network.
        sequence_length: tensor, batch sequence length.

    Returns:
        last_hidden: tensor, retrieved last hidden state.
    """
    last_indices = tf.range(0, batch_size) * len_sequence + (sequence_length - 1)
    last_hidden = tf.gather(outputs, last_indices)
    return last_hidden


def lrelu(x, alpha=0.1):
    """Leaky ReLU activation.

    Args:
        x(Tensor): Input from the previous layer.
        alpha(float): Parameter for if x < 0.

    Returns:
        Output tensor
    """
    # linear = 0.5 * x + 0.5 * tf.abs(x)
    # leaky = 0.5 * alpha * x - 0.5 * alpha * tf.abs(x)
    # output = leaky + linear

    linear = tf.add(
        tf.multiply(0.5, x),
        tf.multiply(0.5, tf.abs(x))
    )
    half = tf.multiply(0.5, alpha)
    leaky = tf.subtract(
        tf.multiply(half, x),
        tf.multiply(half, tf.abs(x))
    )
    output = tf.add(linear, leaky)

    return output


def flatten(x):
    """Flatten a tensor for the fully connected layer.
    Each image in a batch is flattened.

    Args:
        x(Tensor): 4-D tensor of shape [batch, height, width, channels] to be flattened
            to the shape of [batch, height * width * channels]

    Returns:
        Flattened tensor.
    """
    return tf.reshape(x, shape=[-1, np.prod(x.get_shape().as_list()[1:])])


def fully_conn(x, num_output, name='fc',
               activation='lrelu', keep_prob=1.):
    """Fully connected layer, this is is last parts of convnet.
    Fully connect layer requires each image in the batch be flattened.

    Args:
        x: Input from the previous layer.
        num_output: Output size of the fully connected layer.
        name: Name for the fully connected layer variable scope.
        activation: Set to True to add a leaky relu after fully connected
            layer. Set this argument to False if this is the final layer.
        keep_prob: Keep probability for dropout layers, if keep probability is 1
            there is no dropout. Defaults 1.

    Returns:
        Output tensor.
    """
    with tf.variable_scope(name):
        weights = tf.get_variable(name='fc_w',
                                  shape=[x.get_shape().as_list()[-1], num_output],
                                  initializer=tf.random_normal_initializer(stddev=0.02))
        biases = tf.get_variable(name='fc_b',
                                 shape=[num_output],
                                 initializer=tf.zeros_initializer())

        output = tf.nn.bias_add(tf.matmul(x, weights), biases)
        output = tf.nn.dropout(output, keep_prob=keep_prob)

        if activation == 'sigmoid':
            output = tf.sigmoid(output)
        elif activation == 'lrelu':
            output = lrelu(output)
        else:
            pass

        return output


def batch_normalize(x, epsilon=1e-5):
    """Batch normalization for the network.

    Args:
        x: Input tensor from the previous layer.
        epsilon: Variance epsilon.

    Returns:
        Output tensor.
    """
    with tf.variable_scope('batch_norm'):
        mean, variance = tf.nn.moments(x, axes=[0, 1, 2])

        scale = tf.get_variable('bn_scale',
                                shape=[x.get_shape().as_list()[-1]],
                                initializer=tf.ones_initializer())
        offset = tf.get_variable('bn_bias',
                                 shape=[x.get_shape().as_list()[-1]],
                                 initializer=tf.zeros_initializer())
        normalized = tf.nn.batch_normalization(x=x, mean=mean,
                                               variance=variance, offset=offset,
                                               scale=scale, variance_epsilon=epsilon)
        return normalized


def weigh_attention(source_hidden, target_hidden=None, name='attention_score'):
    """Function for computing attention score.

    Args:
        target_hidden: Tensor, target hidden state.
        source_hidden: Tensor, source hidden state.
        name: str, name for variable scope.

    Returns:
        attention: Tensor, computed Luong attention weights.
    """
    with tf.variable_scope(name):
        if target_hidden is None:
            target_hidden = tf.get_variable(name='target_hidden',
                                            shape=[source_hidden.get_shape().as_list()[-1]],
                                            initializer=tf.random_normal_initializer())

        weights = tf.get_variable(name='weights',
                                  shape=[source_hidden.get_shape().as_list()[-1]],
                                  initializer=tf.truncated_normal_initializer())

        weighed_hidden = tf.multiply(weights, source_hidden)
        # Reshape for broadcasting
        weighed_hidden = tf.reshape(weighed_hidden, shape=[-1, target_hidden.get_shape().as_list()[-1]])
        target_hidden = tf.reshape(target_hidden, shape=[-1, target_hidden.get_shape().as_list()[-1]])

        score = tf.matmul(weighed_hidden, target_hidden, transpose_b=True)
        score = tf.reshape(score, shape=[-1, source_hidden.get_shape().as_list()[-2]])

        attention = tf.nn.softmax(score)

        return attention


def get_context_vector(source_hidden, attention_weights):
    """Compute the context vector give source hidden state and attention
    weights.

    Args:
        source_hidden: Tensor, source hidden state.
        attention_weights: Tensor, attention weights.

    Returns:

    """
    attention_weights = tf.expand_dims(attention_weights, -1)
    context_vector = tf.reduce_sum(tf.multiply(attention_weights, source_hidden),
                                   axis=1)
    context_vector = tf.reshape(context_vector,
                                shape=[-1, source_hidden.get_shape().as_list()[-1]])
    return context_vector
