import { db } from "./server/_core/db";
import { sql } from "drizzle-orm";

async function reloadCache() {
  try {
    console.log("Reloading PostgREST Schema Cache...");
    await db.execute(sql`NOTIFY pgrst, 'reload schema'`);
    console.log("Success! Cache reloaded.");
  } catch (err) {
    console.error("Failed to reload cache:", err);
  } finally {
    process.exit(0);
  }
}
reloadCache();
