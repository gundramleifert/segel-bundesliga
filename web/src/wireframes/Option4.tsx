
import { DIVISIONS, NEWS, PHOTOS, STANDINGS, VIDEOS } from "./data";
import { LeaguePage } from "./LeaguePage";
import { Footer, HeroMedia, Img, MyArea, PressList, SectionTitle, StandingsTable, TopBar, VideoTile } from "./kit";
import { formatDate, useWireframe } from "./nav";

const GALLERY = [
  PHOTOS.stMoritz, PHOTOS.helgaNrv, PHOTOS.kiel4, PHOTOS.helgaBahn, PHOTOS.kiel12,
  PHOTOS.eckernfoerde, PHOTOS.alster, PHOTOS.kiel17, PHOTOS.mueritz,
];

/** Option 4 — "Magazine", after deutsche-segelbundesliga.de: pictures carry the page. A
 *  quiet editorial bar, an editorial mosaic, a dark video band, a gallery and a press centre;
 *  the tables shrink to a widget. */
export function Option4() {
  const { league } = useWireframe();
  return (
    <div className="min-h-dvh bg-white text-ink">
      <TopBar variant="editorial" right={<MyArea />} />
      {league ? <LeaguePage league={league} /> : <Home />}
      <Footer />
    </div>
  );
}

function Home() {
  const [lead, ...rest] = NEWS;
  return (
    <main>
      <section className="mx-auto grid grid-cols-[minmax(0,1fr)] max-w-7xl gap-2 px-4 py-6 lg:grid-cols-2 lg:px-8">
        <a href="#" className="group relative block aspect-[4/3] overflow-hidden rounded-xl bg-slate-900 lg:aspect-auto lg:min-h-[32rem]">
          <HeroMedia photo={lead.photo} className="transition group-hover:scale-105" />
          <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-slate-950/90 via-transparent p-6 text-white">
            <p className="text-xs font-semibold uppercase tracking-widest text-white/70">{lead.league}</p>
            <h1 className="mt-1 text-3xl font-extrabold leading-tight sm:text-4xl">{lead.title}</h1>
          </div>
        </a>
        <div className="grid grid-cols-2 gap-2">
          {rest.slice(0, 4).map((item) => (
            <a key={item.title} href="#" className="group relative block aspect-square overflow-hidden rounded-xl bg-slate-900 lg:aspect-auto">
              <Img photo={item.photo} className="transition group-hover:scale-105" />
              <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-slate-950/90 via-transparent p-3 text-white">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-white/70">{item.league}</p>
                <h2 className="line-clamp-3 text-sm font-bold leading-snug sm:text-base">{item.title}</h2>
              </div>
            </a>
          ))}
        </div>
      </section>

      <section className="bg-slate-950 py-12 text-white">
        <div className="mx-auto max-w-7xl px-4 lg:px-8">
          <SectionTitle light more="YouTube">Videos</SectionTitle>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-3">
            <VideoTile video={VIDEOS[0]} className="lg:col-span-2" />
            <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
              {VIDEOS.slice(1, 3).map((video) => <VideoTile key={video.src} video={video} />)}
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl space-y-16 px-4 py-12 lg:px-8">
        <section>
          <SectionTitle>Standings at a glance</SectionTitle>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-3">
            {DIVISIONS.filter((l) => (STANDINGS[l.slug] ?? []).length).map((l) => (
              <div key={l.slug}>
                <p className="mb-2 font-semibold">{l.short}</p>
                <StandingsTable slug={l.slug} limit={3} dense />
              </div>
            ))}
          </div>
        </section>

        <section>
          <SectionTitle more="All galleries">Photos</SectionTitle>
          <div className="columns-2 gap-2 md:columns-3 [&>*]:mb-2">
            {GALLERY.map((p, i) => (
              <div key={p.src} className={`overflow-hidden rounded-lg ${i % 3 === 0 ? "aspect-[3/4]" : "aspect-[4/3]"}`}>
                <Img photo={p} />
              </div>
            ))}
          </div>
        </section>

        <section className="grid grid-cols-[minmax(0,1fr)] gap-8 rounded-2xl bg-slate-900 p-6 text-white lg:grid-cols-3 lg:p-10">
          <div className="lg:col-span-2">
            <SectionTitle light more="Archive">Press centre</SectionTitle>
            <PressList dark />
          </div>
          <div className="space-y-4">
            {[
              ["Press kit 2026", "Logos, fact sheet, photos of the leagues"],
              ["Accreditation", "Apply for a matchday — on the water or ashore"],
              ["Press contact", "presse@segelliga.example.com"],
            ].map(([title, text]) => (
              <a key={title} href="#" className="block rounded-xl bg-white/5 p-4 hover:bg-white/10">
                <p className="font-semibold">{title}</p>
                <p className="text-sm text-white/60">{text}</p>
              </a>
            ))}
          </div>
        </section>

        <section>
          <SectionTitle more="@segelliga">Instagram</SectionTitle>
          <div className="grid grid-cols-3 gap-1 sm:grid-cols-6">
            {[PHOTOS.kiel7, PHOTOS.helga2022, PHOTOS.kiel10, PHOTOS.alster, PHOTOS.helgaNrv, PHOTOS.stMoritz].map((p) => (
              <div key={p.src} className="aspect-square overflow-hidden"><Img photo={p} /></div>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">Last update {formatDate("2026-10-08")}</p>
        </section>
      </div>
    </main>
  );
}
