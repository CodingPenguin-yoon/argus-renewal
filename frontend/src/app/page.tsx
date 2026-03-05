import { HomeDashboard } from "@/components/news/home-dashboard";
import { getHomeData } from "@/lib/server/data-service";

export default async function HomePage() {
  const data = await getHomeData();

  return <HomeDashboard macroNews={data.macroNews} allNews={data.news} events={data.events} />;
}
