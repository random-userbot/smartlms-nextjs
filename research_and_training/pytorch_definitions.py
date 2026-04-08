import torch
import torch.nn as nn

# ──────────────────────────────────────────────────────────────
# Shared Blocks
# ──────────────────────────────────────────────────────────────

class MultiScaleConv(nn.Module):
    """Multi-scale 1D convolutions for local temporal patterns."""
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv3 = nn.Conv1d(in_ch, out_ch // 3, kernel_size=3, padding=1)
        self.conv5 = nn.Conv1d(in_ch, out_ch // 3, kernel_size=5, padding=2)
        self.conv7 = nn.Conv1d(in_ch, out_ch - 2 * (out_ch // 3), kernel_size=7, padding=3)
        self.bn = nn.BatchNorm1d(out_ch)
        self.act = nn.GELU()

    def forward(self, x):
        # x: (B, T, C) -> (B, C, T) for conv
        x = x.transpose(1, 2)
        out = torch.cat([self.conv3(x), self.conv5(x), self.conv7(x)], dim=1)
        out = self.act(self.bn(out))
        return out.transpose(1, 2)  # (B, T, out_ch)


class SEBlock(nn.Module):
    """Squeeze-and-Excitation for feature recalibration."""
    def __init__(self, channels, reduction=8):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(channels, channels // reduction),
            nn.GELU(),
            nn.Linear(channels // reduction, channels),
            nn.Sigmoid(),
        )

    def forward(self, x):
        # x: (B, T, C)
        se = x.mean(dim=1)  # (B, C) global avg pool over time
        se = self.fc(se).unsqueeze(1)  # (B, 1, C)
        return x * se


class TemporalAttention(nn.Module):
    """Soft attention over LSTM time steps."""
    def __init__(self, hidden_dim):
        super().__init__()
        self.attn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1, bias=False),
        )

    def forward(self, lstm_out):
        # lstm_out: (B, T, H)
        scores = self.attn(lstm_out).squeeze(-1)  # (B, T)
        weights = torch.softmax(scores, dim=1)     # (B, T)
        context = (lstm_out * weights.unsqueeze(-1)).sum(dim=1)  # (B, H)
        return context, weights


# ──────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────

class BiLSTMAttention(nn.Module):
    """From train_model_v3.py: BiLSTM with soft temporal attention."""
    def __init__(self, input_dim, hidden=128, layers=2, dropout=0.4):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden, layers, batch_first=True,
                            bidirectional=True, dropout=dropout if layers > 1 else 0)
        self.attention = TemporalAttention(hidden * 2)
        self.bn = nn.BatchNorm1d(hidden * 2)
        self.head = nn.Sequential(
            nn.Linear(hidden * 2, 128), nn.GELU(), nn.Dropout(0.4),
            nn.Linear(128, 64), nn.GELU(), nn.Dropout(0.3),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        out, _ = self.lstm(x)           # (B, T, 2*hidden)
        context, _ = self.attention(out) # (B, 2*hidden) - attended
        context = self.bn(context)
        return self.head(context)


class BiLSTMGRUHybrid(nn.Module):
    """From train_model_v4.py: Multi-scale Conv + BiLSTM + BiGRU."""
    def __init__(self, n_feat, hidden=192, n_layers=3, dropout=0.4):
        super().__init__()
        self.ms_conv = MultiScaleConv(n_feat, hidden)
        self.se = SEBlock(hidden)
        self.lstm = nn.LSTM(hidden, hidden, n_layers, batch_first=True,
                            bidirectional=True, dropout=dropout)
        self.gru = nn.GRU(hidden * 2, hidden, 1, batch_first=True, bidirectional=True)
        self.attn = nn.Sequential(
            nn.Linear(hidden * 2, hidden),
            nn.Tanh(),
            nn.Linear(hidden, 1, bias=False),
        )
        self.head = nn.Sequential(
            nn.LayerNorm(hidden * 2),
            nn.Linear(hidden * 2, 128),
            nn.GELU(),
            nn.Dropout(0.4),
            nn.Linear(128, 64),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        x = self.ms_conv(x)
        x = self.se(x)
        lstm_out, _ = self.lstm(x)
        gru_out, _ = self.gru(lstm_out)
        # Attention pooling
        scores = self.attn(gru_out).squeeze(-1)
        weights = torch.softmax(scores, dim=1)
        context = (gru_out * weights.unsqueeze(-1)).sum(dim=1)
        return self.head(context)


class TemporalTransformer(nn.Module):
    """From train_model_v4.py: Transformer Encoder."""
    def __init__(self, n_features, d_model=128, nhead=8, num_layers=4,
                 dim_ff=256, dropout=0.3, max_seq_len=120):
        super().__init__()
        self.d_model = d_model

        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(n_features, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout * 0.5),
        )

        # [CLS] token
        self.cls_token = nn.Parameter(torch.randn(1, 1, d_model) * 0.02)

        # Positional encoding (learnable)
        self.pos_embed = nn.Parameter(torch.randn(1, max_seq_len + 1, d_model) * 0.02)

        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_ff,
            dropout=dropout,
            activation='gelu',
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Classification head
        self.head = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1),
        )

    def forward(self, x):
        B, T, _ = x.shape
        # Project features
        x = self.input_proj(x)  # (B, T, d_model)

        # Prepend [CLS] token
        cls = self.cls_token.expand(B, -1, -1)  # (B, 1, d_model)
        x = torch.cat([cls, x], dim=1)  # (B, T+1, d_model)

        # Add positional encoding
        x = x + self.pos_embed[:, :T + 1, :]

        # Transformer
        x = self.encoder(x)  # (B, T+1, d_model)

        # Use [CLS] token output
        cls_out = x[:, 0, :]  # (B, d_model)
        return self.head(cls_out)


class CNNBiLSTMAttention(nn.Module):
    """From train_model_v2.py: CNN + BiLSTM + Attention."""
    def __init__(self, input_dim, n_out=1):
        super().__init__()
        
        # CNN block (operates on feature dimension per timestep)
        self.cnn = nn.Sequential(
            nn.Conv1d(input_dim, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Conv1d(128, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.2),
        )
        
        self.lstm = nn.LSTM(64, 64, 2, batch_first=True, bidirectional=True, dropout=0.3)
        
        # Attention
        self.attention = nn.Sequential(
            nn.Linear(128, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
        )
        
        self.classifier = nn.Sequential(
            nn.BatchNorm1d(128),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, n_out),
        )

    def forward(self, x):
        # x: (batch, seq_len, features) — pre-normalized
        
        # CNN expects (batch, channels, seq_len)
        x = x.permute(0, 2, 1)
        x = self.cnn(x)
        x = x.permute(0, 2, 1)  # Back to (batch, seq_len, features)
        
        # BiLSTM
        lstm_out, _ = self.lstm(x)  # (batch, seq_len, 128)
        
        # Attention
        attn_weights = self.attention(lstm_out)  # (batch, seq_len, 1)
        attn_weights = torch.softmax(attn_weights, dim=1)
        context = torch.sum(lstm_out * attn_weights, dim=1)  # (batch, 128)
        
        return self.classifier(context)


class BiLSTMModel(nn.Module):
    """From train_model_v2.py: Simple BiLSTM."""
    def __init__(self, input_dim, hidden_dim=64, n_layers=2, n_out=1, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim, n_layers,
            batch_first=True, bidirectional=True, dropout=dropout,
        )
        self.bn = nn.BatchNorm1d(hidden_dim * 2)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, n_out),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]  # Last timestep
        out = self.bn(out)
        return self.fc(out)
