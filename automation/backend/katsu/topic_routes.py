from fastapi import HTTPException, Query

from .topics import MAX_EXCLUDED_IDS, TopicService


def attach_topic_routes(app, store):
    app.state.topics = TopicService(store.root)

    @app.get('/api/topics')
    async def topics(offset: int = Query(0, ge=0, le=1000), limit: int = Query(5, ge=1, le=5),
                     exclude: str | None = Query(None, max_length=6000, pattern=r'^[0-9a-f]{20}(?:,[0-9a-f]{20})*$')):
        exclude_ids = tuple(exclude.split(',')) if exclude is not None else None
        if exclude_ids is not None and len(exclude_ids) > MAX_EXCLUDED_IDS:
            raise HTTPException(422, 'Too many excluded topic IDs.')
        return await app.state.topics.page(offset, limit, exclude_ids=exclude_ids)
