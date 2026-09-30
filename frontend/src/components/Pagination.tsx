interface Props {
  offset: number;
  limit: number;
  total: number;
  onOffsetChange: (offset: number) => void;
}

export default function Pagination({ offset, limit, total, onOffsetChange }: Props) {
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, total);
  return (
    <div className="pagination">
      <span className="muted">
        {start}-{end} of {total.toLocaleString()}
      </span>
      <button disabled={offset === 0} onClick={() => onOffsetChange(Math.max(0, offset - limit))}>
        Prev
      </button>
      <button disabled={offset + limit >= total} onClick={() => onOffsetChange(offset + limit)}>
        Next
      </button>
    </div>
  );
}
