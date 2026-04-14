export async function fetchPlayers() {
  const res = await fetch('/data/players.json');
  if (!res.ok) throw new Error(`Failed to load players data: ${res.status}`);
  return res.json();
}
