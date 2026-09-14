"use client";
import { useEffect, useState } from "react";
import { apiFetch, Page } from "../../lib/api";
type Patient = { id: string; mrn: string; first_name: string; last_name: string; phone_number: string; preferred_language: string; consent_status: boolean };
export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function fetchPatients() {
    setLoading(true); setError(null);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      setPatients(await apiFetch<Patient[]>(`/api/v1/patients?${params.toString()}`));
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to load patients"); }
    finally { setLoading(false); }
  }
  useEffect(() => { fetchPatients(); }, []);
  return (
    <Page kicker="CARE POPULATION" title="Patients" sub="Searchable directory. Click an MRN for timeline + eligibility.">
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <input className="input" placeholder="Search by MRN or name" value={search}
          onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && fetchPatients()} />
        <button className="btn" onClick={fetchPatients}>Search</button>
      </div>
      {loading && <p>Loading…</p>}
      {error && <p className="alert err">{error}</p>}
      <div className="table-wrap"><table className="table">
        <thead><tr><th>MRN</th><th>Name</th><th>Phone</th><th>Lang</th><th>Consent</th></tr></thead>
        <tbody>{patients.map((p) => (
          <tr key={p.id}>
            <td><a href={`/patients/${p.id}`}><strong>{p.mrn}</strong></a></td>
            <td>{p.first_name} {p.last_name}</td><td>{p.phone_number}</td><td>{p.preferred_language}</td>
            <td>{p.consent_status ? <span className="pill green">Yes</span> : <span className="pill red">No</span>}</td>
          </tr>))}</tbody>
      </table></div>
    </Page>);
}

