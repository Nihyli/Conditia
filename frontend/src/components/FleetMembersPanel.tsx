import { useCallback, useEffect, useState } from "react";
import {
  addFleetMember,
  getFleetMembers,
  removeFleetMember,
  updateFleetMember,
  type ApiFleetMember,
} from "../api";

const ROLES: ApiFleetMember["role"][] = ["viewer", "inspector", "admin"];

export function FleetMembersPanel({
  canManage,
  currentUserId,
}: {
  canManage: boolean;
  currentUserId: string | null;
}) {
  const [members, setMembers] = useState<ApiFleetMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newUserId, setNewUserId] = useState("");
  const [newRole, setNewRole] = useState<ApiFleetMember["role"]>("viewer");
  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setMembers(await getFleetMembers());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load fleet members");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const userId = newUserId.trim();
    if (!userId) return;
    setBusyUserId(userId);
    setError(null);
    try {
      await addFleetMember({ user_id: userId, role: newRole });
      setNewUserId("");
      setNewRole("viewer");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add member");
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleRoleChange(userId: string, role: ApiFleetMember["role"]) {
    setBusyUserId(userId);
    setError(null);
    try {
      await updateFleetMember(userId, role);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update role");
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleRemove(userId: string) {
    if (!window.confirm(`Remove ${userId} from this fleet?`)) return;
    setBusyUserId(userId);
    setError(null);
    try {
      await removeFleetMember(userId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove member");
    } finally {
      setBusyUserId(null);
    }
  }

  return (
    <section className="panel">
      <div className="panel__head">
        <h2 className="panel__title">Fleet members</h2>
      </div>

      {error ? (
        <p className="error-note" style={{ padding: "0 var(--space-20)" }}>
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="muted" style={{ padding: "0 var(--space-20) var(--space-16)" }}>
          Loading members…
        </p>
      ) : members.length === 0 ? (
        <div className="empty">
          <div className="empty__title">No members yet</div>
          <p className="muted">
            {canManage
              ? "Add a user ID below to grant fleet access."
              : "No fleet memberships are configured."}
          </p>
        </div>
      ) : (
        <div className="insp-list">
          {members.map((member) => (
            <div key={member.user_id} className="insp-row">
              <span className="insp-row__id mono">{member.user_id}</span>
              <span className="insp-row__meta">
                {member.user_id === currentUserId ? (
                  <span className="insp-row__truck">You</span>
                ) : null}
              </span>
              {canManage ? (
                <>
                  <select
                    className="select"
                    value={member.role}
                    disabled={busyUserId === member.user_id}
                    onChange={(e) =>
                      void handleRoleChange(
                        member.user_id,
                        e.target.value as ApiFleetMember["role"]
                      )
                    }
                    aria-label={`Role for ${member.user_id}`}
                  >
                    {ROLES.map((role) => (
                      <option key={role} value={role}>
                        {role}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="ghost-btn"
                    disabled={busyUserId === member.user_id}
                    onClick={() => void handleRemove(member.user_id)}
                  >
                    Remove
                  </button>
                </>
              ) : (
                <span className="status-badge status-badge--neutral">{member.role}</span>
              )}
            </div>
          ))}
        </div>
      )}

      {canManage ? (
        <form
          className="filter-row"
          style={{ padding: "var(--space-16) var(--space-20)" }}
          onSubmit={(e) => void handleAdd(e)}
        >
          <label className="form-field">
            <span>User ID</span>
            <input
              className="select"
              placeholder="uuid or auth subject"
              value={newUserId}
              onChange={(e) => setNewUserId(e.target.value)}
              disabled={busyUserId !== null}
            />
          </label>
          <label className="form-field form-field--inline">
            <span>Role</span>
            <select
              value={newRole}
              onChange={(e) =>
                setNewRole(e.target.value as ApiFleetMember["role"])
              }
              disabled={busyUserId !== null}
            >
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            className="primary-btn"
            disabled={!newUserId.trim() || busyUserId !== null}
          >
            Add member
          </button>
        </form>
      ) : (
        <p className="muted" style={{ padding: "0 var(--space-20) var(--space-16)" }}>
          Only fleet admins can add or edit members.
        </p>
      )}
    </section>
  );
}
