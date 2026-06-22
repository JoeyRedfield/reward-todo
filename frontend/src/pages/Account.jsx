import { useCallback, useEffect, useState } from "react";
import {
  changePassword,
  createAccessToken,
  fetchAccessTokens,
  fetchAccountProfile,
  fetchAccountSessions,
  getErrorMessage,
  revokeAccessToken,
  revokeAccountSession,
  revokeOtherAccountSessions,
} from "../api/client";

const TOKEN_EXPIRY_PRESETS = [
  { value: "1h", label: "1 小时", seconds: 3600 },
  { value: "1d", label: "1 天", seconds: 86400 },
  { value: "7d", label: "7 天", seconds: 604800 },
  { value: "30d", label: "30 天", seconds: 2592000 },
  { value: "90d", label: "90 天", seconds: 7776000 },
  { value: "180d", label: "180 天", seconds: 15552000 },
  { value: "365d", label: "365 天", seconds: 31536000 },
  { value: "never", label: "永不过期", seconds: 0 },
  { value: "custom", label: "自定义", seconds: null },
];

function formatDateTime(value) {
  if (!value) {
    return "未记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatExpiryDateTime(value) {
  if (!value) {
    return "永不过期";
  }
  return formatDateTime(value);
}

export default function AccountPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState("");
  const [profile, setProfile] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [tokens, setTokens] = useState([]);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);

  const [tokenName, setTokenName] = useState("");
  const [tokenType, setTokenType] = useState("api");
  const [tokenPassword, setTokenPassword] = useState("");
  const [tokenExpiryPreset, setTokenExpiryPreset] = useState("30d");
  const [customExpirySeconds, setCustomExpirySeconds] = useState("7200");
  const [tokenSubmitting, setTokenSubmitting] = useState(false);
  const [generatedToken, setGeneratedToken] = useState(null);

  function handleTokenNameChange(value) {
    setTokenName(value);
    setGeneratedToken(null);
  }

  function handleTokenTypeChange(value) {
    setTokenType(value);
    setGeneratedToken(null);
  }

  function handleTokenPasswordChange(value) {
    setTokenPassword(value);
    setGeneratedToken(null);
  }

  function handleTokenExpiryPresetChange(value) {
    setTokenExpiryPreset(value);
    setGeneratedToken(null);
  }

  function handleCustomExpirySecondsChange(value) {
    setCustomExpirySeconds(value);
    setGeneratedToken(null);
  }

  const loadPage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileData, sessionData, tokenData] = await Promise.all([
        fetchAccountProfile(),
        fetchAccountSessions(),
        fetchAccessTokens(),
      ]);
      setProfile(profileData);
      setSessions(sessionData.items || []);
      setTokens(tokenData.items || []);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "账号页加载失败，请稍后重试。"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPage();
  }, [loadPage]);

  const apiTokenEnabled = profile?.api_token_enabled ?? true;
  const mcpEnabled = profile?.mcp_enabled ?? true;
  const availableTokenTypes = [];
  if (apiTokenEnabled) {
    availableTokenTypes.push("api");
  }
  if (mcpEnabled) {
    availableTokenTypes.push("mcp");
  }

  useEffect(() => {
    if (!availableTokenTypes.length) {
      if (generatedToken !== null) {
        setGeneratedToken(null);
      }
      return;
    }

    if (!availableTokenTypes.includes(tokenType)) {
      setTokenType(availableTokenTypes[0]);
      setGeneratedToken(null);
    }
  }, [availableTokenTypes, generatedToken, tokenType]);

  async function handleChangePassword(event) {
    event.preventDefault();
    setPasswordSubmitting(true);
    setError(null);
    setSuccessMessage("");
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_new_password: confirmNewPassword,
      });
      setSuccessMessage("密码已更新");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
      await loadPage();
    } catch (submitError) {
      setError(getErrorMessage(submitError, "修改密码失败"));
    } finally {
      setPasswordSubmitting(false);
    }
  }

  async function handleCreateToken(event) {
    event.preventDefault();
    if (!availableTokenTypes.includes(tokenType)) {
      setError("当前服务未启用所选 Token 类型。");
      return;
    }

    const selectedPreset = TOKEN_EXPIRY_PRESETS.find((item) => item.value === tokenExpiryPreset);
    let expiresInSeconds = selectedPreset?.seconds ?? 2592000;
    if (tokenExpiryPreset === "custom") {
      expiresInSeconds = Number.parseInt(customExpirySeconds, 10);
      if (!Number.isFinite(expiresInSeconds) || expiresInSeconds <= 0) {
        setError("自定义过期秒数必须大于 0");
        return;
      }
    }

    setTokenSubmitting(true);
    setError(null);
    setSuccessMessage("");
    try {
      const token = await createAccessToken({
        name: tokenName,
        token_type: tokenType,
        password: tokenPassword,
        expires_in_seconds: expiresInSeconds,
      });
      setGeneratedToken(token);
      setTokenName("");
      setTokenPassword("");
      setSuccessMessage("Token 已生成，请立即保存。");
      await loadPage();
    } catch (submitError) {
      setError(getErrorMessage(submitError, "生成 Token 失败"));
    } finally {
      setTokenSubmitting(false);
    }
  }

  async function handleRevokeSession(sessionId) {
    setError(null);
    setSuccessMessage("");
    try {
      await revokeAccountSession(sessionId);
      setSuccessMessage("会话已撤销。");
      await loadPage();
    } catch (revokeError) {
      setError(getErrorMessage(revokeError, "撤销会话失败"));
    }
  }

  async function handleRevokeOtherSessions() {
    setError(null);
    setSuccessMessage("");
    try {
      await revokeOtherAccountSessions();
      setSuccessMessage("其他会话已全部退出。");
      await loadPage();
    } catch (revokeError) {
      setError(getErrorMessage(revokeError, "退出其他会话失败"));
    }
  }

  async function handleRevokeToken(tokenId) {
    setError(null);
    setSuccessMessage("");
    try {
      await revokeAccessToken(tokenId);
      setSuccessMessage("Token 已撤销。");
      if (generatedToken?.id === tokenId) {
        setGeneratedToken(null);
      }
      await loadPage();
    } catch (revokeError) {
      setError(getErrorMessage(revokeError, "撤销 Token 失败"));
    }
  }

  const currentSession = sessions.find((session) => session.is_current);
  const otherSessions = sessions.filter((session) => !session.is_current);
  const effectiveTokenType = generatedToken?.token_type ?? tokenType;
  const showNeverExpireWarning = generatedToken
    ? generatedToken.expires_at == null
    : tokenExpiryPreset === "never";
  const showMcpWarning = effectiveTokenType === "mcp";
  const generatedTokenConfig =
    generatedToken?.token_type === "mcp"
      ? JSON.stringify(
          {
            mcpServers: {
              "reward-todo-mcp": {
                type: "streamable-http",
                url: generatedToken.mcp_url,
                headers: {
                  Authorization: `Bearer ${generatedToken.token}`,
                },
              },
            },
          },
          null,
          2
        )
      : generatedToken?.token
        ? [
            `export REWARDTOOL_SERVER_BASEURL="${generatedToken.api_base_url}"`,
            `export REWARDTOOL_TOKEN="${generatedToken.token}"`,
            "sh skills/reward-todo/scripts/rewardtools.sh projects-list",
          ].join("\n")
        : "";

  return (
    <div className="page-stack">
      <header className="page-head">
        <div className="page-head-main">
          <div className="page-kicker">Account Center</div>
          <h1>账号设置</h1>
          <p className="page-head-copy">
            在这里维护账号资料、登录安全、会话状态，以及给 Agent 或 MCP 使用的访问
            Token。
          </p>
        </div>
        <aside className="page-stamp">
          <div className="page-stamp-label">安全摘要</div>
          <div className="page-stamp-value">
            最近登录、密码更新和外部访问能力都集中在这个页面。
          </div>
        </aside>
      </header>

      {loading ? <div className="loading-card">加载中...</div> : null}

      {!loading ? (
        <>
          {error ? <div className="error-banner">{error}</div> : null}
          {successMessage ? <div className="success-banner">{successMessage}</div> : null}

          <section className="panel account-section">
            <div className="panel-head">
              <h2>账号资料</h2>
            </div>
            <div className="account-overview-grid">
              <article className="summary-card">
                <div className="summary-label">用户名</div>
                <div className="summary-value account-metric">{profile?.username ?? "-"}</div>
                <div className="summary-hint">账号已完成基础认证，可直接访问工作台。</div>
              </article>
              <article className="summary-card">
                <div className="summary-label">创建时间</div>
                <div className="summary-value account-metric">
                  {formatDateTime(profile?.created_at)}
                </div>
                <div className="summary-hint">用于追踪账号启用时间。</div>
              </article>
            </div>
            <div className="account-meta-list">
              <div className="account-meta-row">
                <span>最近登录</span>
                <strong>{formatDateTime(profile?.last_login_at)}</strong>
              </div>
              <div className="account-meta-row">
                <span>最近改密</span>
                <strong>{formatDateTime(profile?.password_changed_at)}</strong>
              </div>
            </div>
          </section>

          <section className="panel account-section">
            <div className="panel-head">
              <h2>最近登录与会话</h2>
              {otherSessions.length ? (
                <button className="ghost-button" type="button" onClick={handleRevokeOtherSessions}>
                  退出其他会话
                </button>
              ) : null}
            </div>
            <div className="account-session-grid">
              <article className="task-item account-session-card">
                <div className="task-row">
                  <strong>当前会话</strong>
                  <span className="status-pill">本机已登录</span>
                </div>
                <div className="account-meta-list">
                  <div className="account-meta-row">
                    <span>最近活动</span>
                    <strong>{formatDateTime(currentSession?.last_seen_at)}</strong>
                  </div>
                  <div className="account-meta-row">
                    <span>过期时间</span>
                    <strong>{formatDateTime(currentSession?.expires_at)}</strong>
                  </div>
                </div>
              </article>

              <div className="session-stack">
                <h3 className="account-subheading">其他设备会话</h3>
                {otherSessions.length ? (
                  otherSessions.map((session) => (
                    <article className="task-item" key={session.id}>
                      <div className="task-row">
                        <strong>其他会话</strong>
                        <button
                          className="ghost-button"
                          type="button"
                          aria-label={`撤销会话 ${session.id}`}
                          onClick={() => handleRevokeSession(session.id)}
                        >
                          撤销
                        </button>
                      </div>
                      <div className="account-meta-list">
                        <div className="account-meta-row">
                          <span>最近活动</span>
                          <strong>{formatDateTime(session.last_seen_at)}</strong>
                        </div>
                        <div className="account-meta-row">
                          <span>过期时间</span>
                          <strong>{formatDateTime(session.expires_at)}</strong>
                        </div>
                      </div>
                    </article>
                  ))
                ) : (
                  <p className="empty-copy">当前没有其他活跃会话。</p>
                )}
              </div>
            </div>
          </section>

          <section className="panel account-section">
            <div className="panel-head">
              <h2>密码修改</h2>
            </div>
            <p className="account-section-copy">
              修改密码后，建议检查其他设备会话和 Token 是否仍需保留。
            </p>
            <form className="form-stack account-form-grid" onSubmit={handleChangePassword}>
              <div className="account-inline-fields">
                <label>
                  当前密码
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                  />
                </label>
                <label>
                  新密码
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                  />
                </label>
              </div>
              <label>
                确认新密码
                <input
                  type="password"
                  value={confirmNewPassword}
                  onChange={(event) => setConfirmNewPassword(event.target.value)}
                />
              </label>
              <button className="primary-button" type="submit" disabled={passwordSubmitting}>
                更新密码
              </button>
            </form>
          </section>

          <section className="panel account-section">
            <div className="panel-head">
              <h2>Token 管理</h2>
            </div>
            <p className="account-section-copy">
              为脚本、Agent 或 MCP 客户端生成单独的访问凭据，便于按用途管理和撤销。
            </p>
            {!availableTokenTypes.length ? (
              <div className="warning-banner">当前服务未启用 Agent API Token 或 MCP。</div>
            ) : (
              <>
                {showNeverExpireWarning ? (
                  <div className="warning-banner">这个 Token 永不过期，请妥善保管。</div>
                ) : null}
                {showMcpWarning ? (
                  <div className="warning-banner">
                    连接第三方客户端时，请注意它们及其使用的大语言模型也可能访问你的私有数据。
                  </div>
                ) : null}
                <form className="form-stack account-form-grid" onSubmit={handleCreateToken}>
                  <div className="account-token-grid">
                    <label>
                      Token 名称
                      <input
                        type="text"
                        value={tokenName}
                        onChange={(event) => handleTokenNameChange(event.target.value)}
                      />
                    </label>
                    <label>
                      Token 类型
                      <select
                        value={tokenType}
                        onChange={(event) => handleTokenTypeChange(event.target.value)}
                      >
                        {availableTokenTypes.map((type) => (
                          <option key={type} value={type}>
                            {type}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      过期时间
                      <select
                        value={tokenExpiryPreset}
                        onChange={(event) => handleTokenExpiryPresetChange(event.target.value)}
                      >
                        {TOKEN_EXPIRY_PRESETS.map((preset) => (
                          <option key={preset.value} value={preset.value}>
                            {preset.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      当前密码
                      <input
                        type="password"
                        value={tokenPassword}
                        onChange={(event) => handleTokenPasswordChange(event.target.value)}
                      />
                    </label>
                  </div>
                  {tokenExpiryPreset === "custom" ? (
                    <label>
                      自定义过期秒数
                      <input
                        type="number"
                        min="1"
                        max="31536000"
                        value={customExpirySeconds}
                        onChange={(event) => handleCustomExpirySecondsChange(event.target.value)}
                      />
                    </label>
                  ) : null}
                  <button className="primary-button" type="submit" disabled={tokenSubmitting}>
                    生成 Token
                  </button>
                </form>
              </>
            )}

            {generatedToken ? (
              <div className="generated-token-card">
                <label>
                  新 Token
                  <input readOnly value={generatedToken.token} />
                </label>
                <label>
                  {generatedToken.token_type === "mcp" ? "MCP 地址" : "API 地址"}
                  <input
                    readOnly
                    value={generatedToken.mcp_url || generatedToken.api_base_url || ""}
                  />
                </label>
                <label>
                  {generatedToken.token_type === "mcp" ? "MCP 客户端配置" : "Agent Skill 初始化"}
                  <textarea readOnly value={generatedTokenConfig} rows={generatedToken.token_type === "mcp" ? 10 : 3} />
                </label>
              </div>
            ) : null}

            <div className="token-list">
              {tokens.length ? (
                tokens.map((token) => (
                  <article className="template-card" key={token.id}>
                    <div className="task-row">
                      <strong>{token.name}</strong>
                      <button
                        className="ghost-button"
                        type="button"
                        aria-label={`撤销 Token ${token.id}`}
                        onClick={() => handleRevokeToken(token.id)}
                      >
                        撤销
                      </button>
                    </div>
                    <div className="account-meta-list">
                      <div className="account-meta-row">
                        <span>类型</span>
                        <strong>{token.token_type}</strong>
                      </div>
                      <div className="account-meta-row">
                        <span>创建时间</span>
                        <strong>{formatDateTime(token.created_at)}</strong>
                      </div>
                      <div className="account-meta-row">
                        <span>最近使用</span>
                        <strong>{formatDateTime(token.last_seen_at)}</strong>
                      </div>
                      <div className="account-meta-row">
                        <span>过期时间</span>
                        <strong>{formatExpiryDateTime(token.expires_at)}</strong>
                      </div>
                    </div>
                  </article>
                ))
              ) : (
                <p className="empty-copy">还没有生成任何访问令牌。</p>
              )}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
