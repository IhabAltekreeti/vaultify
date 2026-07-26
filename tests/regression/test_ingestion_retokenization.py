import re

from vaultify.services.ingestion import CanonicalChunkerV2


class RetokenizingFakeTokenizer:
    """Tokenizer whose decode -> encode round-trip expands token count.

    Original alphanumeric input tokens are one token each. Decoding appends a
    punctuation marker, so re-tokenizing the decoded text yields an extra token.
    This reproduces the class of behavior observed with a real WordPiece tokenizer
    without depending on external model downloads in committed pytest.
    """

    def __init__(self):
        self._token_to_id = {}
        self._id_to_token = {}
        self._next_id = 1000

    def _tokens(self, text):
        return re.findall(r"[A-Za-z0-9_]+|[^\w\s]", str(text or ""))

    def _id(self, token):
        if token not in self._token_to_id:
            token_id = self._next_id
            self._next_id += 1
            self._token_to_id[token] = token_id
            self._id_to_token[token_id] = token
        return self._token_to_id[token]

    def __call__(self, text, *, add_special_tokens, **_kwargs):
        ids = [self._id(token) for token in self._tokens(text)]
        if add_special_tokens:
            ids = [101] + ids + [102]
        return {"input_ids": ids}

    def decode(self, token_ids, **_kwargs):
        pieces = []
        for token_id in token_ids:
            token = self._id_to_token.get(token_id)
            if token is None:
                continue
            if token.isalnum() or token.replace("_", "").isalnum():
                pieces.append(token + "!")
            else:
                pieces.append(token)
        return " ".join(pieces)


class RetokenizingFakeModel:
    max_seq_length = 256

    def __init__(self):
        self.tokenizer = RetokenizingFakeTokenizer()


def test_oversized_table_row_refits_after_decode_retokenization_expands():
    chunker = CanonicalChunkerV2(RetokenizingFakeModel())
    table_prefix = "Section: Revenue\nTable columns:\n| Metric | Value |"
    row = "| Oversized row | " + " ".join(["123456"] * 700) + " |"

    chunks = chunker.split_oversized_table_row(
        row,
        table_prefix,
        "Revenue",
    )

    assert len(chunks) > 1
    assert all(chunk["chunk_type"] == "table" for chunk in chunks)
    assert all(chunk["section"] == "Revenue" for chunk in chunks)
    assert max(
        chunker.count_embedding_tokens(chunk["text"])
        for chunk in chunks
    ) <= 240
