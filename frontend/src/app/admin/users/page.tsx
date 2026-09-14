"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../../lib/api";

type User = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  hospital_id: string | null;
};

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<User[]>("/api/v1/users")
      .then(setUsers)
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load users"));
  }, []);

  return (
    <Page kicker="HOSPITAL ADMIN" title="Users" sub="Staff members at this hospital.">
      {err && <p className="alert err" role="alert">{err}</p>}
      <div className="panel" style={{ marginTop: 14 }}>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Active</th>
                <th>Hospital ID</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td><strong>{u.full_name}</strong></td>
                  <td>{u.email}</td>
                  <td>{u.role.replace("_", " ")}</td>
                  <td>{u.is_active ? "Yes" : "No"}</td>
                  <td>{u.hospital_id?.slice(0, 8) ?? "N/A"}</td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr><td colSpan={5} className="sub">No users found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Page>
  );
}
