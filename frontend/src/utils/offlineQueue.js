/**
 * Offline-first assessment queue (IndexedDB via `idb`).
 *
 * When a test video is recorded/selected with no network, we stash the raw video
 * File plus its assessment metadata here. On reconnect (or app boot) the queue is
 * flushed by re-running the real upload against the backend.
 *
 * This module has NO dependency on api.js — flushQueue() receives an uploader
 * callback — so there is no import cycle (api.js imports from here).
 */

import { openDB } from 'idb';

const DB_NAME = 'sai-talentai';
const DB_VERSION = 1;
const STORE = 'pendingAssessments';

let _dbPromise = null;
function getDB() {
  if (!_dbPromise) {
    _dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
        }
      }
    });
  }
  return _dbPromise;
}

function notifyChanged() {
  window.dispatchEvent(new CustomEvent('queue:changed'));
}

/**
 * Persist one pending assessment.
 * item: { file: Blob, athlete_id, test_type, reference_height_cm }
 */
export async function enqueueAssessment(item) {
  const db = await getDB();
  const record = { ...item, createdAt: new Date().toISOString() };
  const id = await db.add(STORE, record);
  notifyChanged();
  return id;
}

export async function getQueued() {
  const db = await getDB();
  return db.getAll(STORE);
}

export async function removeQueued(id) {
  const db = await getDB();
  await db.delete(STORE, id);
  notifyChanged();
}

export async function queueCount() {
  try {
    const db = await getDB();
    return db.count(STORE);
  } catch (_) {
    return 0;
  }
}

/**
 * Replay every queued assessment through `uploader(item)`.
 * - On success: remove the item.
 * - On network failure: stop (keep the rest for the next reconnect).
 * - On server rejection (e.g. corrupt/too-short video): drop the item so it
 *   cannot permanently jam the queue.
 * Returns the number of items successfully submitted.
 */
export async function flushQueue(uploader) {
  const items = await getQueued();
  let flushed = 0;
  for (const item of items) {
    try {
      await uploader(item);
      await removeQueued(item.id);
      flushed += 1;
    } catch (err) {
      const networkFailure = (typeof navigator !== 'undefined' && navigator.onLine === false)
        || err instanceof TypeError; // fetch() throws TypeError when the network is unreachable
      if (networkFailure) {
        break; // still offline — try again later
      }
      // Server rejected this specific item; it will never succeed → drop it.
      console.warn('Dropping un-submittable queued assessment:', err?.message || err);
      await removeQueued(item.id);
    }
  }
  return flushed;
}
