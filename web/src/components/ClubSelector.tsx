import { TransferList } from "./TransferList";

/** Two-pane transfer list for choosing which clubs participate — `TransferList` with a
 * club's name and short name. Kept as its own name because three admin panels use it. */
export function ClubSelector({
  clubs,
  selectedIds,
  toggle,
  id,
  testId,
}: {
  clubs: { id: number; name: string; short_name: string }[];
  selectedIds: Set<number>;
  toggle: (id: number) => void;
  id?: string;
  testId?: string;
}) {
  return (
    <TransferList
      id={id}
      testId={testId ?? "clubs-transfer-list"}
      available={clubs.filter((club) => !selectedIds.has(club.id))}
      selected={clubs.filter((club) => selectedIds.has(club.id))}
      label={(club) => club.name}
      secondary={(club) => club.short_name}
      matches={(club, term) =>
        club.name.toLowerCase().includes(term) || club.short_name.toLowerCase().includes(term)
      }
      onSelect={(club) => toggle(club.id)}
      onDeselect={(club) => toggle(club.id)}
    />
  );
}
