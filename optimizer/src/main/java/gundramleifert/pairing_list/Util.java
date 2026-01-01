package gundramleifert.pairing_list;

import gundramleifert.pairing_list.configs.ScheduleConfig;
import gundramleifert.pairing_list.types.Flight;
import gundramleifert.pairing_list.types.Race;
import gundramleifert.pairing_list.types.SameShuttle;
import gundramleifert.pairing_list.types.Schedule;

import java.util.*;


public class Util {

  public static MatchMatrix getMatchMatrix(Schedule schedule, int numTeams, int numBoats) {
    return getMatchMatrix(schedule, schedule.size() - 1, numTeams, numBoats);
  }

  public static MatchMatrix getMatchMatrix(Schedule schedule, int flight, int numTeams, int numBoats) {
    MatchMatrix mm = new MatchMatrix(numTeams, numBoats);
    for (int i = 0; i <= flight; i++) {
      mm.add(schedule.get(i));
    }
    return mm;
  }

  public static void shuffle(byte[] bytes, Random rnd) {
    for (int i = 0; i < bytes.length; i++) {
      int j = rnd.nextInt(bytes.length);
      byte swap = bytes[i];
      bytes[i] = bytes[j];
      bytes[j] = swap;
    }
  }

  public static void printCount(ScheduleConfig props, Schedule schedule) {
    int[] cnts = new int[schedule.size() + 1];
    MatchMatrix matchMatrix = schedule.getMatchMatrix();
    StringBuilder sb1 = new StringBuilder();
    for (int i = 0; i < matchMatrix.mat.length; i++) {
      byte[] vec = matchMatrix.mat[i];
      for (int j = 0; j < i; j++) {
        cnts[vec[j]]++;
      }
    }
    int max_value = 1;
    for (int i = 0; i < cnts.length; i++) {
      if (cnts[i] > 0) {
        max_value = i;
      }
    }
    StringBuilder sb = new StringBuilder();
    for (int j = 0; j <= max_value; j++) {
      sb1.append(String.format("%4d", j));
      sb.append(cnts[j] == 0 ? "    " : String.format("%4d", cnts[j] * 2));
    }
    System.out.println(sb1.toString());
    System.out.println(sb.toString());
  }

  public static void printCount(int[] counts, boolean startAtOne) {
    int max_value = 1;
    for (int i = 0; i < counts.length; i++) {
      if (counts[i] > 0) {
        max_value = i;
      }
    }
    StringBuilder sb1 = new StringBuilder();
    StringBuilder sb = new StringBuilder();
    for (int j = 0; j <= max_value; j++) {
      sb1.append(String.format("%4d", (startAtOne ? j + 1 : j)));
      sb.append(counts[j] == 0 ? "    " : String.format("%4d", counts[j]));
    }
    System.out.println(sb1.toString());
    System.out.println(sb.toString());
  }

  public static void printMatchMatrix(ScheduleConfig props, Schedule schedule) {
    MatchMatrix mm = schedule.getMatchMatrix();
    StringBuilder sb1 = new StringBuilder();
    sb1.append(String.format("%3s", "-"));
    for (int j = 0; j < props.bytes.length; j++) {
      sb1.append(String.format("%3s", props.bytes[j]));
    }
    System.out.println(sb1.toString());
    for (int i = 0; i < mm.mat.length; i++) {
      byte[] vec = mm.mat[i];
      StringBuilder sb = new StringBuilder();
      sb.append(String.format("%3s", i));
      for (int j = 0; j < vec.length; j++) {
        byte t2 = vec[j];
        //String v = String.format("%3d", t2);
        sb.append(String.format("%3d", t2));
      }
      System.out.println(sb.toString());
    }
  }

  private static SameShuttle teamsOnSameShuttles(Race before, Race middle, Race after, Random random) {
    SameShuttle sameShuttle = new SameShuttle(middle);
    for (int i = 0; i < before.teams.length; i++) {
      byte t1 = before.teams[i];
      for (int j = 0; j < after.teams.length; j++) {
        byte t2 = after.teams[j];
        if (t1 == t2 && i < middle.teams.length) {
          sameShuttle.boats.add(middle.teams[i]);
        }
      }
    }
    if (sameShuttle.boats.size() % 2 == 1) {
      sameShuttle.boats.remove(random.nextInt(sameShuttle.boats.size()));
    }
    if (sameShuttle.boats.size() > 0) {
      return sameShuttle;
    }
    return null;
  }

  public static Map<Race, SameShuttle> teamsOnSameShuttles(Schedule schedule, Random random) {
    Map<Race, SameShuttle> res = new HashMap<>();
    for (int i = 1; i < schedule.size(); i++) {
      Flight flight1 = schedule.get(i - 1);
      Flight flight2 = schedule.get(i);
      Race race1 = flight1.races[flight1.races.length - 2];
      Race race2 = flight1.races[flight1.races.length - 1];
      Race race3 = flight2.races[0];
      Race race4 = flight2.races[1];
      SameShuttle sameShuttle1 = teamsOnSameShuttles(race1, race2, race3, random);
      SameShuttle sameShuttle2 = teamsOnSameShuttles(race2, race3, race4, random);
      if (sameShuttle1 != null) {
        res.put(race2, sameShuttle1);
      }
      if (sameShuttle2 != null) {
        res.put(race3, sameShuttle2);
      }
    }
    return res;
  }

  public static byte[] copy(byte[] bytes, int from, int length) {
    byte[] res = new byte[length];
    System.arraycopy(bytes, from, res, 0, length);
    return res;
  }


  public static Schedule shuffleBoats(Schedule schedule, Random random) {
    schedule = schedule.copy();
    for (int i = 0; i < schedule.size(); i++) {
      Flight flight = schedule.get(i);
      for (Race race : flight.races) {
        shuffle(race.teams, random);
      }
    }
    return schedule;
  }

  public static Flight getRandomFlight(ScheduleConfig config, Random random) {
    Race[] races = new Race[config.getRaces()];
    byte[] teams = config.bytes;
    Util.shuffle(teams, random);
    int off = 0;
    for (int j = races.length; j > 0; j--) {
      int remaining = (teams.length - off) / j;
      Race race = new Race(Util.copy(teams, off, remaining));
      Arrays.sort(race.teams);
      races[j - 1] = race;
      off += race.teams.length;
      if (off > config.numTeams) {
        break;
      }
    }
    Arrays.sort(races, Comparator.comparingInt(race -> race.teams[0]));
    return new Flight(races);
  }

  public static void shuffleTeams(Flight flight, Random random) {
    for (Race race : flight.races) {
      Util.shuffle(race.teams, random);
    }
  }

  public static Flight copyFlightAndShuffleTeams(Flight flight, Random random) {
    flight = flight.copy();
    shuffleTeams(flight, random);
    return flight;
  }

  public static Schedule getRandomSchedule(ScheduleConfig properties, Random random) {
    Schedule schedule = new Schedule(properties);
    for (int i = 0; i < properties.flights; i++) {
      schedule.add(getRandomFlight(properties, random));
    }
    return schedule;

  }

}
