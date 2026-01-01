package gundramleifert.pairing_list;

import gundramleifert.pairing_list.configs.ScheduleConfig;
import gundramleifert.pairing_list.types.Flight;
import gundramleifert.pairing_list.types.Race;
import gundramleifert.pairing_list.types.Schedule;

import java.util.Arrays;
import java.util.Comparator;
import java.util.Random;

public class MutationUtil {

    public static Schedule swapBoats(Schedule schedule, Random random) {
        int f_idx = random.nextInt(schedule.size());
        Flight f = schedule.get(f_idx).copy();
        int races = f.races.length;
        int r_idx = random.nextInt(races);
        Race r = f.races[r_idx];
        int boats = r.teams.length;
        int b_idx1 = random.nextInt(boats);
        int b_idx2 = (b_idx1 + 1 + random.nextInt(boats - 1)) % boats;
        byte boat = r.teams[b_idx1];
        r.teams[b_idx1] = r.teams[b_idx2];
        r.teams[b_idx2] = boat;
        Schedule res = schedule.copy(f_idx, f);
        // NO sort!!
        return res;
    }
    public static Schedule swapBoatsDeepCopy(Schedule schedule, Random random) {
        int f_idx = random.nextInt(schedule.size());
        Flight f = schedule.get(f_idx).copy();
        int races = f.races.length;
        int r_idx = random.nextInt(races);
        Race r = f.races[r_idx];
        int boats = r.teams.length;
        int b_idx1 = random.nextInt(boats);
        int b_idx2 = (b_idx1 + 1 + random.nextInt(boats - 1)) % boats;
        byte boat = r.teams[b_idx1];
        r.teams[b_idx1] = r.teams[b_idx2];
        r.teams[b_idx2] = boat;
        // NO sort!!
        return schedule.deepCopy(f_idx,f);
    }

    public static Schedule swapRaces(Schedule schedule, Random random) {
        int f_idx = random.nextInt(schedule.size());
        Flight f = schedule.get(f_idx).copy();
        int races = f.races.length;
        int r1_idx = random.nextInt(races);
        int r2_idx = (r1_idx + 1 + random.nextInt(races - 1)) % races;
        Race race = f.races[r1_idx];
        f.races[r1_idx] = f.races[r2_idx];
        f.races[r2_idx] = race;
        Schedule res = schedule.copy(f_idx, f);
        return res;
    }
    public static Schedule swapRacesDeepCopy(Schedule schedule, Random random) {
        int f_idx = random.nextInt(schedule.size());
        Flight f = schedule.get(f_idx).copy();
        int races = f.races.length;
        int r1_idx = random.nextInt(races);
        int r2_idx = (r1_idx + 1 + random.nextInt(races - 1)) % races;
        Race race = f.races[r1_idx];
        f.races[r1_idx] = f.races[r2_idx];
        f.races[r2_idx] = race;
        return schedule.deepCopy(f_idx,f);
    }

    public static void swapBetweenRaces(Schedule schedule, Random random) {
        Flight f = schedule.get(schedule.size() - 1);
        int races = f.races.length;
        int r1_idx = random.nextInt(races);
        int r2_idx = (r1_idx + 1 + random.nextInt(races - 1)) % races;
        Race r1 = f.races[r1_idx];
        Race r2 = f.races[r2_idx];
        int t1_idx = random.nextInt(r1.teams.length);
        int t2_idx = random.nextInt(r2.teams.length);
        byte team1 = r1.teams[t1_idx];
        r1.teams[t1_idx] = r2.teams[t2_idx];
        r2.teams[t2_idx] = team1;
        Arrays.sort(r1.teams);
        Arrays.sort(r2.teams);
        Arrays.sort(f.races, Comparator.comparingInt(race -> race.teams[0]));
    }

//    public static Schedule swapBetweenRaces(Schedule schedule, int flightIndex, Random random) {
//        Schedule res = schedule.copy();
//        Flight f = res.get(flightIndex);
//        f = swapBetweenRaces(f, random);
//        res.set(flightIndex,f);
//        return res;
//    }

}
