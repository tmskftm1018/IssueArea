export function LoadingNewsState() {
  return (
    <div className="skeletons" role="status" aria-label="뉴스 불러오는 중">
      {[1, 2, 3].map((item) => (
        <div className="skeleton" key={item}>
          <div />
          <div />
          <div />
        </div>
      ))}
    </div>
  );
}

export function NewsErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="state-box" role="alert">
      <h3>뉴스 데이터를 불러오지 못했습니다.</h3>
      <p>API 연결을 확인한 뒤 다시 시도해 주세요.</p>
      <button className="primary-button" onClick={onRetry}>
        다시 시도
      </button>
    </div>
  );
}

export function EmptyNewsState({ onReset }: { onReset: () => void }) {
  return (
    <div className="state-box">
      <h3>조건에 맞는 뉴스가 없습니다.</h3>
      <p>기간을 넓히거나 검색 조건을 바꿔보세요.</p>
      <button className="primary-button" onClick={onReset}>
        필터 초기화
      </button>
    </div>
  );
}
