export async function fetchPlayers() {
  console.log('Fetching players data from /data/players.json');
  const res = await fetch('/data/players.json');
  console.log('Response status:', res.status);
  if (!res.ok) {
    console.error('Failed to load players data:', res.status, res.statusText);
    throw new Error(`Failed to load players data: ${res.status}`);
  }
  const data = await res.json();
  console.log('Players data loaded:', data.length, 'players');
  return data;
}
